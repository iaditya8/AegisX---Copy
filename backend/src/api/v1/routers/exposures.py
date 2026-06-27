import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.user import StandardResponse
from src.domain.entities.exposure import (
    ExposureSeverity,
    ExposureStatus,
    ExposureType,
    ExposureResponse,
)
from src.infrastructure.database.models import Scope, User, Asset
from src.infrastructure.database.session import get_db
from src.services.exposure_service import ExposureService
from src.services.exposure_history_service import ExposureHistoryService
from src.services.exposure_correlation_service import ExposureCorrelationService
from src.services.exposure_prioritization_service import ExposurePrioritizationService
from src.services.exposure_drift_service import ExposureDriftService
from src.services.exposure_snapshot_service import ExposureSnapshotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/exposures", tags=["exposures"])


class CreateExposureRequest(BaseModel):
    title: str
    description: str
    exposure_type: ExposureType
    severity: ExposureSeverity
    asset_id: uuid.UUID
    target: str
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

@router.get("", response_model=StandardResponse[List[ExposureResponse]])
async def list_exposures(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[ExposureResponse]]:
    """List all exposures, filtered by scope ownership."""
    exposures = ExposureService.get_all_exposures()

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        # Fetch asset details to check scopes
        filtered = []
        for e in exposures:
            asset = await db.get(Asset, e.asset_id)
            if asset and asset.scope_id in allowed_scopes:
                filtered.append(e)
        exposures = filtered

    data = [ExposureService.to_response(e) for e in exposures]
    return StandardResponse(data=data)


@router.get("/open", response_model=StandardResponse[List[ExposureResponse]])
async def list_open_exposures(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[ExposureResponse]]:
    """List all open exposures, filtered by scope ownership."""
    exposures = ExposureService.get_all_exposures()
    exposures = [e for e in exposures if e.status == ExposureStatus.OPEN]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        filtered = []
        for e in exposures:
            asset = await db.get(Asset, e.asset_id)
            if asset and asset.scope_id in allowed_scopes:
                filtered.append(e)
        exposures = filtered

    data = [ExposureService.to_response(e) for e in exposures]
    return StandardResponse(data=data)


@router.get("/critical", response_model=StandardResponse[List[ExposureResponse]])
async def list_critical_exposures(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[ExposureResponse]]:
    """List all critical exposures, filtered by scope ownership."""
    exposures = ExposureService.get_all_exposures()
    exposures = [e for e in exposures if e.severity == ExposureSeverity.CRITICAL]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        filtered = []
        for e in exposures:
            asset = await db.get(Asset, e.asset_id)
            if asset and asset.scope_id in allowed_scopes:
                filtered.append(e)
        exposures = filtered

    data = [ExposureService.to_response(e) for e in exposures]
    return StandardResponse(data=data)


@router.get("/drift", response_model=StandardResponse[dict])
async def check_exposure_drift(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[dict]:
    """Check exposure drift on demand for a scope."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)

    prev_snap = ExposureSnapshotService.get_snapshot(scope_id)
    await ExposureDriftService.check_drift(db, scope_id=scope_id, prev_snapshot=prev_snap)
    new_snap = await ExposureSnapshotService.generate_snapshot(db, scope_id)

    return StandardResponse(data={"snapshot": new_snap})


@router.get("/summary", response_model=StandardResponse[dict])
async def get_exposure_summary(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[dict]:
    """Get summarized exposure stats, filtered by scope ownership."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)

    snap = ExposureSnapshotService.get_snapshot(scope_id)
    return StandardResponse(data=snap)


@router.get("/{exposure_id}", response_model=StandardResponse[ExposureResponse])
async def get_exposure(
    exposure_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[ExposureResponse]:
    """Get detailed view of a single exposure, including ownership checks."""
    exposure = ExposureService.get_exposure(exposure_id)
    if not exposure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exposure {exposure_id} not found",
        )

    await check_asset_ownership(db, exposure.asset_id, current_user)

    data = ExposureService.to_response(exposure)
    return StandardResponse(data=data)


@router.post("", response_model=StandardResponse[ExposureResponse], status_code=status.HTTP_201_CREATED)
async def create_exposure(
    payload: CreateExposureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ExposureResponse]:
    """Manually register a new exposure, with asset scope validation."""
    await check_asset_ownership(db, payload.asset_id, current_user)

    exposure = await ExposureService.create_or_sync_exposure(
        db=db,
        title=payload.title,
        description=payload.description,
        exposure_type=payload.exposure_type,
        severity=payload.severity,
        asset_id=payload.asset_id,
        target=payload.target,
        owner=payload.owner,
    )

    data = ExposureService.to_response(exposure)
    return StandardResponse(data=data)


@router.post("/{exposure_id}/validate", response_model=StandardResponse[ExposureResponse])
async def validate_exposure(
    exposure_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ExposureResponse]:
    """Transition exposure to VALIDATED."""
    exposure = ExposureService.get_exposure(exposure_id)
    if not exposure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exposure {exposure_id} not found",
        )

    await check_asset_ownership(db, exposure.asset_id, current_user)

    try:
        updated = ExposureService.validate_exposure(exposure_id)
        return StandardResponse(data=ExposureService.to_response(updated))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{exposure_id}/accept", response_model=StandardResponse[ExposureResponse])
async def accept_exposure(
    exposure_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ExposureResponse]:
    """Transition exposure to ACCEPTED."""
    exposure = ExposureService.get_exposure(exposure_id)
    if not exposure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exposure {exposure_id} not found",
        )

    await check_asset_ownership(db, exposure.asset_id, current_user)

    try:
        updated = ExposureService.accept_exposure(exposure_id)
        return StandardResponse(data=ExposureService.to_response(updated))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{exposure_id}/mitigate", response_model=StandardResponse[ExposureResponse])
async def mitigate_exposure(
    exposure_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ExposureResponse]:
    """Transition exposure to MITIGATED."""
    exposure = ExposureService.get_exposure(exposure_id)
    if not exposure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exposure {exposure_id} not found",
        )

    await check_asset_ownership(db, exposure.asset_id, current_user)

    try:
        updated = ExposureService.mitigate_exposure(exposure_id)
        return StandardResponse(data=ExposureService.to_response(updated))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{exposure_id}/close", response_model=StandardResponse[ExposureResponse])
async def close_exposure(
    exposure_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ExposureResponse]:
    """Transition exposure to CLOSED."""
    exposure = ExposureService.get_exposure(exposure_id)
    if not exposure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exposure {exposure_id} not found",
        )

    await check_asset_ownership(db, exposure.asset_id, current_user)

    try:
        updated = ExposureService.close_exposure(exposure_id)
        return StandardResponse(data=ExposureService.to_response(updated))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
