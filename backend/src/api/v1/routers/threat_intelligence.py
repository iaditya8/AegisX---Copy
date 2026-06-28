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
from src.domain.entities.threat_intel import (
    ThreatIntelStatus,
    ThreatSeverity,
    ThreatIndicatorType,
    ThreatIntelRecordResponse,
    ThreatIntelSnapshotResponse,
    ThreatIntelHistoryEntry,
    ThreatIntelActorResponse,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.campaign_service import CampaignService
from src.services.ioc_correlation_service import IOCCorrelationService
from src.services.ioc_service import IOCRecord, IOCService
from src.services.scope_service import get_scope_by_id
from src.services.threat_actor_service import ThreatActorService
from src.services.threat_intelligence_snapshot_service import ThreatIntelligenceSnapshotService
from src.services.threat_intelligence_service import ThreatIntelligenceService
from src.services.threat_intel_history_service import ThreatIntelHistoryService
from src.services.threat_intel_snapshot_service import ThreatIntelSnapshotService

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


class CreateThreatRequest(BaseModel):
    value: str
    indicator_type: ThreatIndicatorType
    source: str
    tags: List[str]
    scope_id: Optional[uuid.UUID] = None


class FuseThreatRequest(BaseModel):
    confidence: float


@router.post("/", response_model=ThreatIntelRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_threat(
    payload: CreateThreatRequest,
    current_user: User = Depends(RoleChecker(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Create or synchronize a GRC threat intelligence record."""
    if payload.scope_id:
        await check_scope_ownership(db, payload.scope_id, current_user)

    try:
        record = await ThreatIntelligenceService.create_or_sync_threat(
            value=payload.value,
            indicator_type=payload.indicator_type,
            source=payload.source,
            tags=payload.tags,
            scope_id=payload.scope_id,
        )
        return ThreatIntelligenceService.to_response(record)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=List[ThreatIntelRecordResponse])
async def list_threats_endpoint(
    scope_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(RoleChecker(["admin", "analyst", "viewer"])),
    db: AsyncSession = Depends(get_db),
):
    """List GRC threat intelligence records with optional scope filter."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)

    records = ThreatIntelligenceService.get_all_threats()
    if scope_id:
        records = [r for r in records if r.scope_id == scope_id]
    elif current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id in allowed_scopes]

    return [ThreatIntelligenceService.to_response(r) for r in records]


@router.get("/active", response_model=List[ThreatIntelRecordResponse])
async def list_active_threats(
    current_user: User = Depends(RoleChecker(["admin", "analyst", "viewer"])),
    db: AsyncSession = Depends(get_db),
):
    """List active GRC threat intelligence records."""
    records = ThreatIntelligenceService.get_all_threats()
    active = [r for r in records if r.status in (ThreatIntelStatus.ACTIVE, ThreatIntelStatus.IN_TRIAGE, ThreatIntelStatus.FUSED)]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        active = [r for r in active if r.scope_id in allowed_scopes]

    return [ThreatIntelligenceService.to_response(r) for r in active]


@router.get("/fused", response_model=List[ThreatIntelRecordResponse])
async def list_fused_threats(
    current_user: User = Depends(RoleChecker(["admin", "analyst", "viewer"])),
    db: AsyncSession = Depends(get_db),
):
    """List fused GRC threat intelligence records."""
    records = ThreatIntelligenceService.get_all_threats()
    fused = [r for r in records if r.status == ThreatIntelStatus.FUSED]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        fused = [r for r in fused if r.scope_id in allowed_scopes]

    return [ThreatIntelligenceService.to_response(r) for r in fused]


@router.get("/drift", response_model=List[dict])
async def get_threat_drift(
    current_user: User = Depends(RoleChecker(["admin", "analyst", "viewer"])),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve list of emitted drift events from the workflow event system."""
    from src.services.workflow_event_service import WorkflowEventService
    events = WorkflowEventService.get_events()
    threat_drifts = [
        e for e in events
        if e.get("event_type") in ("threat.drift", "threat.score_changed")
    ]
    return threat_drifts


@router.get("/summary")
async def get_summary(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader", "analyst", "viewer"])),
):
    """Retrieve aggregate or scope-specific threat intelligence summary statistics (merged GRC + IOCs)."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)

    # 1. Gather GRC threat intelligence snapshot summary
    grc_snap = ThreatIntelSnapshotService.get_snapshot(scope_id)
    grc_sum = grc_snap["summary"]

    # 2. Gather old threat intelligence IOC stats
    iocs = IOCService.get_all_iocs()
    if scope_id:
        allowed_iocs = [i for i in iocs if i.scope_id == scope_id]
    else:
        if current_user.role not in ("admin", "analyst"):
            allowed_scopes = await get_allowed_scope_ids(db, current_user)
            allowed_iocs = [i for i in iocs if i.scope_id in allowed_scopes]
        else:
            allowed_iocs = iocs

    active_iocs = [i for i in allowed_iocs if i.status == IOCStatus.ACTIVE]
    total_active = len(active_iocs)
    avg_reputation = sum(i.reputation for i in active_iocs) / total_active if total_active > 0 else 0.0

    return {
        # IOC fields
        "total_iocs": len(allowed_iocs),
        "active_iocs": total_active,
        "average_reputation": avg_reputation,
        # GRC Threat Intel fields
        "total_threat_records": grc_sum["total_threat_records"],
        "active_threat_records": grc_sum["active_threat_records"],
        "archived_threat_records": grc_sum["archived_threat_records"],
        "average_fusion_score": grc_sum["average_fusion_score"],
    }


@router.post("/{threat_intel_id}/triage", response_model=ThreatIntelRecordResponse)
async def triage_threat(
    threat_intel_id: uuid.UUID,
    current_user: User = Depends(RoleChecker(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Transition GRC threat status to IN_TRIAGE."""
    record = ThreatIntelligenceService.get_threat(threat_intel_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Threat record not found")

    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    try:
        updated = ThreatIntelligenceService.transition_status(
            threat_intel_id, ThreatIntelStatus.IN_TRIAGE
        )
        return ThreatIntelligenceService.to_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{threat_intel_id}/fuse", response_model=ThreatIntelRecordResponse)
async def fuse_threat(
    threat_intel_id: uuid.UUID,
    payload: FuseThreatRequest,
    current_user: User = Depends(RoleChecker(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Persist calculated fusion confidence score and transition status to FUSED."""
    record = ThreatIntelligenceService.get_threat(threat_intel_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Threat record not found")

    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    try:
        updated = ThreatIntelligenceService.fuse_threat(threat_intel_id, payload.confidence)
        return ThreatIntelligenceService.to_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{threat_intel_id}/archive", response_model=ThreatIntelRecordResponse)
async def archive_threat(
    threat_intel_id: uuid.UUID,
    current_user: User = Depends(RoleChecker(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    """Transition GRC threat status to ARCHIVED (terminal state)."""
    record = ThreatIntelligenceService.get_threat(threat_intel_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Threat record not found")

    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    try:
        updated = ThreatIntelligenceService.transition_status(
            threat_intel_id, ThreatIntelStatus.ARCHIVED
        )
        return ThreatIntelligenceService.to_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{threat_intel_id}", response_model=ThreatIntelRecordResponse)
async def get_threat_detail(
    threat_intel_id: uuid.UUID,
    current_user: User = Depends(RoleChecker(["admin", "analyst", "viewer"])),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific GRC threat intelligence record details."""
    record = ThreatIntelligenceService.get_threat(threat_intel_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Threat record not found")

    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    return ThreatIntelligenceService.to_response(record)


@router.get("/{threat_intel_id}/history", response_model=List[ThreatIntelHistoryEntry])
async def get_threat_history(
    threat_intel_id: uuid.UUID,
    current_user: User = Depends(RoleChecker(["admin", "analyst", "viewer"])),
    db: AsyncSession = Depends(get_db),
):
    """Get historical log of a specific GRC threat intelligence record."""
    record = ThreatIntelligenceService.get_threat(threat_intel_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Threat record not found")

    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    return ThreatIntelHistoryService.get_history(threat_intel_id)
