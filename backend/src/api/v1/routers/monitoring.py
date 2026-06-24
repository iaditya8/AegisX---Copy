import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.monitoring import (
    MonitoringEventResponse,
    MonitoringSnapshotResponse,
)
from src.domain.entities.user import StandardResponse
from src.infrastructure.database.models import Asset, User
from src.infrastructure.database.session import get_db
from src.services.continuous_refresh_service import ContinuousRefreshService
from src.services.scope_service import get_scope_by_id

router = APIRouter(tags=["monitoring"])


async def has_asset_permission(
    db: AsyncSession, asset_id: uuid.UUID, current_user: User
) -> bool:
    """Enforce scope boundary checks for non-admin operators."""
    if current_user.role == "admin":
        return True
    asset = await db.get(Asset, asset_id)
    if not asset or asset.deleted_at is not None:
        return False
    if not asset.scope_id:
        return False
    scope = await get_scope_by_id(db, asset.scope_id)
    if not scope or scope.owner_id != current_user.id:
        return False
    return True


@router.get(
    "/monitoring/events",
    response_model=StandardResponse[List[MonitoringEventResponse]],
)
async def list_events(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[List[MonitoringEventResponse]]:
    """Retrieve all continuous monitoring events."""
    events = ContinuousRefreshService.get_all_events()
    filtered = []
    for e in events:
        if await has_asset_permission(db, e.asset_id, current_user):
            filtered.append(e)
    return StandardResponse[List[MonitoringEventResponse]](
        success=True,
        message="Monitoring events retrieved",
        data=[MonitoringEventResponse.model_validate(e) for e in filtered],
    )


@router.get(
    "/monitoring/assets/{id}",
    response_model=StandardResponse[List[MonitoringEventResponse]],
)
async def get_asset_events(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[List[MonitoringEventResponse]]:
    """Retrieve monitoring events for a specific asset."""
    if not await has_asset_permission(db, id, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permissions to access this asset",
        )
    events = ContinuousRefreshService.get_all_events()
    filtered = [e for e in events if e.asset_id == id]
    return StandardResponse[List[MonitoringEventResponse]](
        success=True,
        message="Asset monitoring events retrieved",
        data=[MonitoringEventResponse.model_validate(e) for e in filtered],
    )


@router.get(
    "/monitoring/findings/{id}",
    response_model=StandardResponse[List[MonitoringEventResponse]],
)
async def get_finding_events(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[List[MonitoringEventResponse]]:
    """Retrieve monitoring events for a specific finding."""
    events = ContinuousRefreshService.get_all_events()
    filtered = [e for e in events if e.finding_id == id]
    # Check permissions
    allowed = []
    for e in filtered:
        if await has_asset_permission(db, e.asset_id, current_user):
            allowed.append(e)
    return StandardResponse[List[MonitoringEventResponse]](
        success=True,
        message="Finding monitoring events retrieved",
        data=[MonitoringEventResponse.model_validate(e) for e in allowed],
    )


@router.get(
    "/monitoring/summary",
    response_model=StandardResponse[MonitoringSnapshotResponse],
)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[MonitoringSnapshotResponse]:
    """Retrieve summary counts of monitoring events."""
    events = ContinuousRefreshService.get_all_events()
    filtered = []
    for e in events:
        if await has_asset_permission(db, e.asset_id, current_user):
            filtered.append(e)

    snapshot = {
        "added_assets": 0,
        "removed_assets": 0,
        "modified_assets": 0,
        "added_findings": 0,
        "resolved_findings": 0,
        "rediscovered_findings": 0,
        "risk_increases": 0,
        "risk_decreases": 0,
        "governance_changes": 0,
    }

    for event in filtered:
        if event.change_type == "ASSET_ADDED":
            snapshot["added_assets"] += 1
        elif event.change_type == "ASSET_REMOVED":
            snapshot["removed_assets"] += 1
        elif event.change_type == "ASSET_MODIFIED":
            snapshot["modified_assets"] += 1
        elif event.change_type == "FINDING_ADDED":
            snapshot["added_findings"] += 1
        elif event.change_type == "FINDING_RESOLVED":
            snapshot["resolved_findings"] += 1
        elif event.change_type == "FINDING_REDISCOVERED":
            snapshot["rediscovered_findings"] += 1
        elif event.change_type == "RISK_INCREASED":
            snapshot["risk_increases"] += 1
        elif event.change_type == "RISK_DECREASED":
            snapshot["risk_decreases"] += 1
        elif event.change_type in [
            "COMPLIANCE_FAILED",
            "COMPLIANCE_RESTORED",
            "RISK_ACCEPTANCE_EXPIRED",
            "GOVERNANCE_DRIFT",
        ]:
            snapshot["governance_changes"] += 1

    return StandardResponse[MonitoringSnapshotResponse](
        success=True,
        message="Monitoring summary retrieved",
        data=MonitoringSnapshotResponse(**snapshot),
    )


@router.get(
    "/monitoring/drift/assets",
    response_model=StandardResponse[List[MonitoringEventResponse]],
)
async def list_asset_drift(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[List[MonitoringEventResponse]]:
    """Retrieve asset drift events."""
    events = ContinuousRefreshService.get_all_events()
    filtered = [
        e
        for e in events
        if e.change_type in ["ASSET_ADDED", "ASSET_MODIFIED", "ASSET_REMOVED"]
    ]
    allowed = []
    for e in filtered:
        if await has_asset_permission(db, e.asset_id, current_user):
            allowed.append(e)
    return StandardResponse[List[MonitoringEventResponse]](
        success=True,
        message="Asset drift events retrieved",
        data=[MonitoringEventResponse.model_validate(e) for e in allowed],
    )


@router.get(
    "/monitoring/drift/findings",
    response_model=StandardResponse[List[MonitoringEventResponse]],
)
async def list_finding_drift(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[List[MonitoringEventResponse]]:
    """Retrieve finding drift events."""
    events = ContinuousRefreshService.get_all_events()
    filtered = [
        e
        for e in events
        if e.change_type
        in [
            "FINDING_ADDED",
            "FINDING_RESOLVED",
            "FINDING_REDISCOVERED",
            "FINDING_MODIFIED",
        ]
    ]
    allowed = []
    for e in filtered:
        if await has_asset_permission(db, e.asset_id, current_user):
            allowed.append(e)
    return StandardResponse[List[MonitoringEventResponse]](
        success=True,
        message="Finding drift events retrieved",
        data=[MonitoringEventResponse.model_validate(e) for e in allowed],
    )


@router.get(
    "/monitoring/drift/risk",
    response_model=StandardResponse[List[MonitoringEventResponse]],
)
async def list_risk_drift(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[List[MonitoringEventResponse]]:
    """Retrieve risk drift events."""
    events = ContinuousRefreshService.get_all_events()
    filtered = [
        e
        for e in events
        if e.change_type in ["RISK_INCREASED", "RISK_DECREASED", "RISK_DRIFT"]
    ]
    allowed = []
    for e in filtered:
        if await has_asset_permission(db, e.asset_id, current_user):
            allowed.append(e)
    return StandardResponse[List[MonitoringEventResponse]](
        success=True,
        message="Risk drift events retrieved",
        data=[MonitoringEventResponse.model_validate(e) for e in allowed],
    )


@router.get(
    "/monitoring/drift/governance",
    response_model=StandardResponse[List[MonitoringEventResponse]],
)
async def list_governance_drift(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[List[MonitoringEventResponse]]:
    """Retrieve governance drift events."""
    events = ContinuousRefreshService.get_all_events()
    filtered = [
        e
        for e in events
        if e.change_type
        in [
            "COMPLIANCE_FAILED",
            "COMPLIANCE_RESTORED",
            "RISK_ACCEPTANCE_EXPIRED",
            "GOVERNANCE_DRIFT",
        ]
    ]
    allowed = []
    for e in filtered:
        if await has_asset_permission(db, e.asset_id, current_user):
            allowed.append(e)
    return StandardResponse[List[MonitoringEventResponse]](
        success=True,
        message="Governance drift events retrieved",
        data=[MonitoringEventResponse.model_validate(e) for e in allowed],
    )
