import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.threat_intelligence import (
    CampaignResponse,
    IOCResponse,
    IOCSeverity,
    IOCStatus,
    IOCType,
    ThreatActorResponse,
    ThreatFeedType,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.campaign_service import CampaignService
from src.services.ioc_correlation_service import IOCCorrelationService
from src.services.ioc_service import IOCRecord, IOCService
from src.services.scope_service import get_scope_by_id
from src.services.threat_actor_service import ThreatActorService
from src.services.threat_intelligence_snapshot_service import ThreatIntelligenceSnapshotService

router = APIRouter(prefix="/threat-intelligence", tags=["threat-intelligence"])


class CreateIOCRequest(BaseModel):
    value: str
    ioc_type: IOCType
    severity: IOCSeverity
    reputation: int
    feed_type: ThreatFeedType
    scope_id: Optional[uuid.UUID] = None
    threat_actors: Optional[List[str]] = None
    campaigns: Optional[List[str]] = None


# --- Helper Checks ---


async def check_scope_ownership(
    db: AsyncSession, scope_id: uuid.UUID, current_user: User
) -> None:
    """Enforce scope ownership check for non-admin users."""
    if current_user.role == "admin":
        return

    scope = await get_scope_by_id(db, scope_id)
    if not scope or scope.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scope not found",
        )

    if scope.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not own this scope",
        )


async def get_allowed_scope_ids(db: AsyncSession, current_user: User) -> set:
    """Retrieve all scope IDs owned by the current non-admin user."""
    if current_user.role == "admin":
        return set()

    q_scopes = select(Scope).where(
        Scope.owner_id == current_user.id, Scope.deleted_at.is_(None)
    )
    res_scopes = await db.execute(q_scopes)
    scopes = res_scopes.scalars().all()
    return {s.id for s in scopes}


def to_ioc_response(ioc: IOCRecord) -> IOCResponse:
    """Map an IOCRecord to an IOCResponse schema."""
    return IOCResponse(
        ioc_id=ioc.ioc_id,
        ioc_fingerprint=ioc.ioc_fingerprint,
        value=ioc.value,
        ioc_type=ioc.ioc_type,
        severity=ioc.severity,
        status=ioc.status,
        reputation=ioc.reputation,
        feed_type=ioc.feed_type,
        created_at=ioc.created_at,
        updated_at=ioc.updated_at,
        scope_id=ioc.scope_id,
        threat_actors=ioc.threat_actors,
        campaigns=ioc.campaigns,
    )


# --- Endpoints ---


@router.get("/iocs", response_model=List[IOCResponse])
async def list_iocs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all IOC records, applying scope filtering for non-admins."""
    iocs = IOCService.get_all_iocs()
    if current_user.role == "admin":
        return [to_ioc_response(ioc) for ioc in iocs]

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    return [to_ioc_response(ioc) for ioc in iocs if ioc.scope_id in allowed_scopes]


@router.get("/iocs/{id}", response_model=IOCResponse)
async def get_ioc(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve details of a specific IOC record."""
    ioc = IOCService.get_ioc(id)
    if not ioc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IOC {id} not found",
        )

    if current_user.role != "admin":
        await check_scope_ownership(db, ioc.scope_id, current_user)

    return to_ioc_response(ioc)


@router.get("/actors", response_model=List[ThreatActorResponse])
async def list_actors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve threat actors, filtering associated IOCs for non-admins."""
    if current_user.role == "admin":
        return ThreatActorService.get_all_actors()

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    profiles = ThreatActorService.get_all_actors()
    filtered_profiles = []
    for p in profiles:
        scope_iocs = [
            ioc.value
            for ioc in IOCService.get_all_iocs()
            if ioc.scope_id in allowed_scopes
            and (p.name in ioc.threat_actors or any(alias in ioc.threat_actors for alias in p.aliases))
        ]
        filtered_profiles.append(
            ThreatActorResponse(
                actor_id=p.actor_id,
                name=p.name,
                description=p.description,
                aliases=p.aliases,
                severity=p.severity,
                status=p.status,
                iocs=scope_iocs,
            )
        )
    return filtered_profiles


@router.get("/campaigns", response_model=List[CampaignResponse])
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve threat campaigns, filtering associated IOCs for non-admins."""
    if current_user.role == "admin":
        return CampaignService.get_all_campaigns()

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    profiles = CampaignService.get_all_campaigns()
    filtered_profiles = []
    for p in profiles:
        scope_iocs = [
            ioc.value
            for ioc in IOCService.get_all_iocs()
            if ioc.scope_id in allowed_scopes
            and (p.name in ioc.campaigns or any(alias in ioc.campaigns for alias in p.aliases))
        ]
        filtered_profiles.append(
            CampaignResponse(
                campaign_id=p.campaign_id,
                name=p.name,
                description=p.description,
                aliases=p.aliases,
                severity=p.severity,
                status=p.status,
                iocs=scope_iocs,
                threat_actors=p.threat_actors,
            )
        )
    return filtered_profiles


@router.get("/correlations")
async def list_correlations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all IOC correlations, applying scope checks for non-admins."""
    correlations = IOCCorrelationService.get_all_correlations()
    if current_user.role == "admin":
        return correlations

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    return [c for c in correlations if c.scope_id in allowed_scopes]


@router.get("/summary")
async def get_summary(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve aggregate or scope-specific threat intelligence summary statistics."""
    if current_user.role != "admin":
        if scope_id:
            await check_scope_ownership(db, scope_id, current_user)
        else:
            allowed_scopes = await get_allowed_scope_ids(db, current_user)
            iocs = IOCService.get_all_iocs()
            allowed_iocs = [i for i in iocs if i.scope_id in allowed_scopes]
            active_iocs = [i for i in allowed_iocs if i.status == IOCStatus.ACTIVE]
            total_active = len(active_iocs)
            avg_reputation = sum(i.reputation for i in active_iocs) / total_active if total_active > 0 else 0.0
            return {
                "total_iocs": len(allowed_iocs),
                "active_iocs": total_active,
                "average_reputation": avg_reputation,
            }

    snapshot = ThreatIntelligenceSnapshotService.get_snapshot(scope_id)
    return snapshot["summary"]


@router.post("/iocs", response_model=IOCResponse, status_code=status.HTTP_201_CREATED)
async def create_ioc(
    request: CreateIOCRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Create or synchronize an IOC record."""
    if current_user.role != "admin":
        if not request.scope_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Non-admin users must specify a scope they own.",
            )
        await check_scope_ownership(db, request.scope_id, current_user)

    try:
        record = IOCService.create_or_sync_ioc(
            value=request.value,
            ioc_type=request.ioc_type,
            severity=request.severity,
            reputation=request.reputation,
            feed_type=request.feed_type,
            scope_id=request.scope_id,
            threat_actors=request.threat_actors,
            campaigns=request.campaigns,
        )
        return to_ioc_response(record)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/iocs/{id}/expire", response_model=IOCResponse)
async def expire_ioc(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition an IOC status to EXPIRED."""
    ioc = IOCService.get_ioc(id)
    if not ioc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IOC {id} not found",
        )

    if current_user.role != "admin":
        await check_scope_ownership(db, ioc.scope_id, current_user)

    try:
        record = IOCService.expire_ioc(id)
        return to_ioc_response(record)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/iocs/{id}/revoke", response_model=IOCResponse)
async def revoke_ioc(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition an IOC status to REVOKED."""
    ioc = IOCService.get_ioc(id)
    if not ioc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IOC {id} not found",
        )

    if current_user.role != "admin":
        await check_scope_ownership(db, ioc.scope_id, current_user)

    try:
        record = IOCService.revoke_ioc(id)
        return to_ioc_response(record)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
