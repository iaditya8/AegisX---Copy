import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.alert import AlertResponse, AlertStatus, AlertType, AlertSeverity
from src.domain.entities.user import StandardResponse
from src.infrastructure.database.models import Asset, Scope, User
from src.infrastructure.database.session import get_db
from src.services.alert_lifecycle_service import AlertLifecycleService, AlertRecord
from src.services.scope_service import get_scope_by_id

router = APIRouter(tags=["alerts"])


class AssignAlertRequest(BaseModel):
    owner_id: Optional[uuid.UUID] = None


class AlertCreate(BaseModel):
    title: str
    description: str
    severity: str
    alert_type: str
    asset_id: Optional[uuid.UUID] = None
    finding_id: Optional[uuid.UUID] = None


# --- Helper Checks ---


async def get_allowed_asset_ids(db: AsyncSession, current_user: User) -> Optional[set]:
    """Retrieve allowed asset IDs for non-admin users based on scope ownership."""
    if current_user.role == "admin":
        return None

    q_scopes = select(Scope).where(
        Scope.owner_id == current_user.id, Scope.deleted_at.is_(None)
    )
    res_scopes = await db.execute(q_scopes)
    scopes = res_scopes.scalars().all()
    scope_ids = {s.id for s in scopes}

    if not scope_ids:
        return set()

    q_assets = select(Asset.id).where(
        Asset.scope_id.in_(scope_ids), Asset.deleted_at.is_(None)
    )
    res_assets = await db.execute(q_assets)
    return set(res_assets.scalars().all())


async def check_alert_ownership(
    db: AsyncSession, alert: AlertRecord, current_user: User
) -> None:
    """Enforce scope ownership check for non-admin operators on a specific alert."""
    if current_user.role == "admin":
        return

    if not alert.asset_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permissions to access this alert",
        )

    asset = await db.get(Asset, alert.asset_id)
    if not asset or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked asset not found",
        )

    if not asset.scope_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permissions to access this asset",
        )

    scope = await get_scope_by_id(db, asset.scope_id)
    if not scope or scope.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permissions to access this asset",
        )


def to_alert_response(a: AlertRecord) -> AlertResponse:
    """Map AlertRecord to Pydantic AlertResponse."""
    return AlertResponse(
        alert_id=a.alert_id,
        alert_fingerprint=a.alert_fingerprint,
        alert_type=a.alert_type,
        severity=a.severity,
        status=a.status,
        asset_id=a.asset_id,
        finding_id=a.finding_id,
        recommendation_id=a.recommendation_id,
        remediation_id=a.remediation_id,
        created_at=a.created_at,
        updated_at=a.updated_at,
        owner=a.owner,
        title=a.title,
        description=a.description,
    )


# --- REST API Endpoints ---


@router.get(
    "/alerts",
    response_model=StandardResponse[List[AlertResponse]],
)
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[AlertResponse]]:
    """List all alerts filtered by user allowed scope assets."""
    allowed_asset_ids = await get_allowed_asset_ids(db, current_user)
    alerts = AlertLifecycleService.get_all_alerts()

    filtered = []
    for a in alerts:
        if allowed_asset_ids is None or a.asset_id in allowed_asset_ids:
            filtered.append(to_alert_response(a))

    return StandardResponse(data=filtered)


@router.get(
    "/alerts/critical",
    response_model=StandardResponse[List[AlertResponse]],
)
async def list_critical_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[AlertResponse]]:
    """List critical severity alerts filtered by user allowed scope assets."""
    allowed_asset_ids = await get_allowed_asset_ids(db, current_user)
    alerts = AlertLifecycleService.get_all_alerts()

    filtered = []
    for a in alerts:
        if a.severity == "CRITICAL":
            if allowed_asset_ids is None or a.asset_id in allowed_asset_ids:
                filtered.append(to_alert_response(a))

    return StandardResponse(data=filtered)


@router.get(
    "/alerts/escalated",
    response_model=StandardResponse[List[AlertResponse]],
)
async def list_escalated_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[AlertResponse]]:
    """List ESCALATED alerts filtered by user allowed scope assets."""
    allowed_asset_ids = await get_allowed_asset_ids(db, current_user)
    alerts = AlertLifecycleService.get_all_alerts()

    filtered = []
    for a in alerts:
        if a.status == AlertStatus.ESCALATED:
            if allowed_asset_ids is None or a.asset_id in allowed_asset_ids:
                filtered.append(to_alert_response(a))

    return StandardResponse(data=filtered)


@router.get(
    "/alerts/owned",
    response_model=StandardResponse[List[AlertResponse]],
)
async def list_owned_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[AlertResponse]]:
    """List active alerts assigned to the current user."""
    allowed_asset_ids = await get_allowed_asset_ids(db, current_user)
    alerts = AlertLifecycleService.get_all_alerts()

    filtered = []
    for a in alerts:
        if a.owner == current_user.id:
            if allowed_asset_ids is None or a.asset_id in allowed_asset_ids:
                filtered.append(to_alert_response(a))

    return StandardResponse(data=filtered)


@router.get(
    "/alerts/{id}",
    response_model=StandardResponse[AlertResponse],
)
async def get_alert_by_id(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[AlertResponse]:
    """Retrieve details of a specific alert."""
    alert = AlertLifecycleService.get_alert(id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    await check_alert_ownership(db, alert, current_user)
    return StandardResponse(data=to_alert_response(alert))


@router.post(
    "/alerts/{id}/acknowledge",
    response_model=StandardResponse[AlertResponse],
)
async def acknowledge_alert(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[AlertResponse]:
    """Transition alert to ACKNOWLEDGED state."""
    alert = AlertLifecycleService.get_alert(id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    await check_alert_ownership(db, alert, current_user)
    try:
        updated = await AlertLifecycleService.transition_alert(
            db, id, AlertStatus.ACKNOWLEDGED, actor_id=current_user.id
        )
        return StandardResponse(data=to_alert_response(updated))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/alerts/{id}/start",
    response_model=StandardResponse[AlertResponse],
)
async def start_alert_investigation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[AlertResponse]:
    """Transition alert to IN_PROGRESS state."""
    alert = AlertLifecycleService.get_alert(id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    await check_alert_ownership(db, alert, current_user)
    try:
        updated = await AlertLifecycleService.transition_alert(
            db, id, AlertStatus.IN_PROGRESS, actor_id=current_user.id
        )
        return StandardResponse(data=to_alert_response(updated))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/alerts/{id}/resolve",
    response_model=StandardResponse[AlertResponse],
)
async def resolve_alert(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[AlertResponse]:
    """Transition alert to RESOLVED state (terminal)."""
    alert = AlertLifecycleService.get_alert(id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    await check_alert_ownership(db, alert, current_user)
    try:
        updated = await AlertLifecycleService.transition_alert(
            db, id, AlertStatus.RESOLVED, actor_id=current_user.id
        )
        return StandardResponse(data=to_alert_response(updated))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/alerts/{id}/suppress",
    response_model=StandardResponse[AlertResponse],
)
async def suppress_alert(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[AlertResponse]:
    """Transition alert to SUPPRESSED state (terminal)."""
    alert = AlertLifecycleService.get_alert(id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    await check_alert_ownership(db, alert, current_user)
    try:
        updated = await AlertLifecycleService.transition_alert(
            db, id, AlertStatus.SUPPRESSED, actor_id=current_user.id
        )
        return StandardResponse(data=to_alert_response(updated))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/alerts/{id}/assign",
    response_model=StandardResponse[AlertResponse],
)
async def assign_alert_owner(
    id: uuid.UUID,
    req: AssignAlertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[AlertResponse]:
    """Assign/reassign alert to an analyst owner."""
    alert = AlertLifecycleService.get_alert(id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    await check_alert_ownership(db, alert, current_user)
    updated = await AlertLifecycleService.assign_alert(
        db, id, req.owner_id, actor_id=current_user.id
    )
    return StandardResponse(data=to_alert_response(updated))


@router.post(
    "/alerts",
    response_model=StandardResponse[AlertResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_alert(
    alert_in: AlertCreate,
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[AlertResponse]:
    alert_id = uuid.uuid4()
    fingerprint = str(uuid.uuid4())
    new_alert = AlertRecord(
        alert_id=alert_id,
        alert_fingerprint=fingerprint,
        alert_type=AlertType(alert_in.alert_type),
        severity=AlertSeverity(alert_in.severity),
        status=AlertStatus.OPEN,
        title=alert_in.title,
        description=alert_in.description,
        asset_id=alert_in.asset_id,
        finding_id=alert_in.finding_id,
    )
    AlertLifecycleService._alerts[alert_id] = new_alert
    AlertLifecycleService._fingerprint_lookup[fingerprint] = alert_id
    return StandardResponse(data=to_alert_response(new_alert))
