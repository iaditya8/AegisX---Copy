import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.user import StandardResponse
from src.domain.entities.security_posture import (
    PostureSeverity,
    RiskStatus,
    RiskCategory,
    SecurityPostureResponse,
)
from src.infrastructure.database.models import Scope, User, Asset
from src.infrastructure.database.session import get_db
from src.services.security_posture_service import SecurityPostureService
from src.services.posture_history_service import PostureHistoryService
from src.services.risk_correlation_service import RiskCorrelationService
from src.services.posture_drift_service import PostureDriftService
from src.services.security_posture_snapshot_service import SecurityPostureSnapshotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/security-posture", tags=["security-posture"])


class CreatePostureRequest(BaseModel):
    title: str
    description: str
    category: RiskCategory
    severity: PostureSeverity
    asset_id: uuid.UUID
    risk_source: str
    owner: Optional[str] = None


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


async def check_asset_ownership(
    db: AsyncSession, asset_id: uuid.UUID, current_user: User
) -> None:
    """Enforce asset ownership based on its scope."""
    asset = await db.get(Asset, asset_id)
    if not asset or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )
    if asset.scope_id:
        await check_scope_ownership(db, asset.scope_id, current_user)


async def get_allowed_scope_ids(db: AsyncSession, current_user: User) -> set:
    """Retrieve all scope IDs owned by the current user."""
    if current_user.role == "admin":
        return set()

    q_scopes = select(Scope).where(
        Scope.owner_id == current_user.id, Scope.deleted_at.is_(None)
    )
    res_scopes = await db.execute(q_scopes)
    scopes = res_scopes.scalars().all()
    return {s.id for s in scopes}


# --- Endpoints ---

@router.get("", response_model=StandardResponse[List[SecurityPostureResponse]])
async def list_postures(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[SecurityPostureResponse]]:
    """List all security postures, filtered by scope ownership."""
    postures = SecurityPostureService.get_all_postures()

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        # Filter postures based on asset scope
        filtered = []
        for p in postures:
            asset = await db.get(Asset, p.asset_id)
            if asset and asset.scope_id in allowed_scopes:
                filtered.append(p)
        postures = filtered

    data = [SecurityPostureService.to_response(p) for p in postures]
    return StandardResponse(data=data)


@router.get("/open", response_model=StandardResponse[List[SecurityPostureResponse]])
async def list_open_postures(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[SecurityPostureResponse]]:
    """List all open security postures, filtered by scope ownership."""
    postures = SecurityPostureService.get_all_postures()
    postures = [p for p in postures if p.status == RiskStatus.OPEN]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        filtered = []
        for p in postures:
            asset = await db.get(Asset, p.asset_id)
            if asset and asset.scope_id in allowed_scopes:
                filtered.append(p)
        postures = filtered

    data = [SecurityPostureService.to_response(p) for p in postures]
    return StandardResponse(data=data)


@router.get("/critical", response_model=StandardResponse[List[SecurityPostureResponse]])
async def list_critical_postures(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[SecurityPostureResponse]]:
    """List all critical security postures, filtered by scope ownership."""
    postures = SecurityPostureService.get_all_postures()
    postures = [p for p in postures if p.severity == PostureSeverity.CRITICAL]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        filtered = []
        for p in postures:
            asset = await db.get(Asset, p.asset_id)
            if asset and asset.scope_id in allowed_scopes:
                filtered.append(p)
        postures = filtered

    data = [SecurityPostureService.to_response(p) for p in postures]
    return StandardResponse(data=data)


@router.get("/drift", response_model=StandardResponse[dict])
async def check_posture_drift(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[dict]:
    """Check posture drift on demand for a scope."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)

    prev_snap = SecurityPostureSnapshotService.get_snapshot(scope_id)
    await PostureDriftService.check_drift(db, scope_id=scope_id, prev_snapshot=prev_snap)
    new_snap = await SecurityPostureSnapshotService.generate_snapshot(db, scope_id)

    return StandardResponse(data={"snapshot": new_snap})


@router.get("/summary", response_model=StandardResponse[dict])
async def get_posture_summary(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[dict]:
    """Get summarized posture stats, filtered by scope ownership."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)

    snap = SecurityPostureSnapshotService.get_snapshot(scope_id)
    return StandardResponse(data=snap)


@router.get("/{posture_id}", response_model=StandardResponse[SecurityPostureResponse])
async def get_posture(
    posture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[SecurityPostureResponse]:
    """Get detailed view of a single posture, including ownership checks."""
    posture = SecurityPostureService.get_posture(posture_id)
    if not posture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Posture {posture_id} not found",
        )

    await check_asset_ownership(db, posture.asset_id, current_user)

    data = SecurityPostureService.to_response(posture)
    return StandardResponse(data=data)


@router.post("", response_model=StandardResponse[SecurityPostureResponse], status_code=status.HTTP_201_CREATED)
async def create_posture(
    payload: CreatePostureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[SecurityPostureResponse]:
    """Manually register a new posture, with asset scope validation."""
    await check_asset_ownership(db, payload.asset_id, current_user)

    asset = await db.get(Asset, payload.asset_id)
    scope_id = asset.scope_id if asset else None

    posture = await SecurityPostureService.create_or_sync_posture(
        title=payload.title,
        description=payload.description,
        category=payload.category,
        severity=payload.severity,
        asset_id=payload.asset_id,
        risk_source=payload.risk_source,
        owner=payload.owner,
        scope_id=scope_id,
    )

    data = SecurityPostureService.to_response(posture)
    return StandardResponse(data=data)


@router.post("/{posture_id}/accept", response_model=StandardResponse[SecurityPostureResponse])
async def accept_posture_risk(
    posture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[SecurityPostureResponse]:
    """Transition posture risk status to ACCEPTED."""
    posture = SecurityPostureService.get_posture(posture_id)
    if not posture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Posture {posture_id} not found",
        )

    await check_asset_ownership(db, posture.asset_id, current_user)

    try:
        updated = SecurityPostureService.accept_risk(posture_id)
        return StandardResponse(data=SecurityPostureService.to_response(updated))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{posture_id}/mitigate", response_model=StandardResponse[SecurityPostureResponse])
async def mitigate_posture_risk(
    posture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[SecurityPostureResponse]:
    """Transition posture risk status to MITIGATED."""
    posture = SecurityPostureService.get_posture(posture_id)
    if not posture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Posture {posture_id} not found",
        )

    await check_asset_ownership(db, posture.asset_id, current_user)

    try:
        updated = SecurityPostureService.mitigate_risk(posture_id)
        return StandardResponse(data=SecurityPostureService.to_response(updated))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{posture_id}/close", response_model=StandardResponse[SecurityPostureResponse])
async def close_posture_record(
    posture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[SecurityPostureResponse]:
    """Transition posture status to CLOSED."""
    posture = SecurityPostureService.get_posture(posture_id)
    if not posture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Posture {posture_id} not found",
        )

    await check_asset_ownership(db, posture.asset_id, current_user)

    try:
        updated = SecurityPostureService.close_posture(posture_id)
        return StandardResponse(data=SecurityPostureService.to_response(updated))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
