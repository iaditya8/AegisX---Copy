import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.user import StandardResponse
from src.domain.entities.cyber_risk_quantification import (
    RiskQuantificationStatus,
    RiskScenarioType,
    CyberRiskResponse,
    RiskForecastResponse,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.cyber_risk_quantification_service import CyberRiskQuantificationService
from src.services.quantified_risk_history_service import QuantifiedRiskHistoryService
from src.services.risk_forecast_service import RiskForecastService
from src.services.risk_trend_service import RiskTrendService
from src.services.risk_quantification_snapshot_service import RiskQuantificationSnapshotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/cyber-risk-quantification", tags=["cyber-risk-quantification"])


class CreateRiskRequest(BaseModel):
    title: str
    description: str
    scenario_type: RiskScenarioType
    frequency_label: str
    impact_label: str
    exposure_value: float
    scope_id: Optional[uuid.UUID] = None


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

@router.get("", response_model=StandardResponse[List[CyberRiskResponse]])
async def list_risks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[CyberRiskResponse]]:
    """List all cyber risk records."""
    records = CyberRiskQuantificationService.get_all_risks()

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [CyberRiskQuantificationService.to_response(r) for r in records]
    return StandardResponse(data=data)


@router.get("/open", response_model=StandardResponse[List[CyberRiskResponse]])
async def get_open_risks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[CyberRiskResponse]]:
    """Get all open cyber risks (non-closed)."""
    records = CyberRiskQuantificationService.get_all_risks()
    records = [r for r in records if r.status != RiskQuantificationStatus.CLOSED]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [CyberRiskQuantificationService.to_response(r) for r in records]
    return StandardResponse(data=data)


@router.get("/critical", response_model=StandardResponse[List[CyberRiskResponse]])
async def get_critical_risks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[CyberRiskResponse]]:
    """Filter to critical risk records (score >= 70.0)."""
    records = CyberRiskQuantificationService.get_all_risks()
    records = [
        r
        for r in records
        if r.inherent_risk_score >= 70.0 or r.residual_risk_score >= 70.0
    ]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [CyberRiskQuantificationService.to_response(r) for r in records]
    return StandardResponse(data=data)


@router.get("/forecasts", response_model=StandardResponse[List[RiskForecastResponse]])
async def get_forecasts(
    risk_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[RiskForecastResponse]]:
    """Get forecasts for a risk record."""
    record = CyberRiskQuantificationService.get_risk(risk_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    data = RiskForecastService.get_forecasts(risk_id, record.annualized_loss_expectancy, record.exposure_value)
    return StandardResponse(data=data)


@router.get("/trends", response_model=StandardResponse[List[float]])
async def get_trends(
    risk_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[float]]:
    """Get trends history for a risk record."""
    record = CyberRiskQuantificationService.get_risk(risk_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    data = RiskTrendService.get_trends(risk_id)
    return StandardResponse(data=data)


@router.get("/drift", response_model=StandardResponse[Dict])
async def get_drift(
    current_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[Dict]:
    """Retrieve risk drift status logs."""
    return StandardResponse(data={"drift_logs": []})


@router.get("/summary", response_model=StandardResponse[Dict])
async def get_summary(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict]:
    """Get summary snapshot of cyber risk quantification posture."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    else:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Non-admin users must specify scope_id",
            )
    snap = await RiskQuantificationSnapshotService.generate_snapshot(db, scope_id)
    return StandardResponse(data=snap)


@router.get("/{id}", response_model=StandardResponse[CyberRiskResponse])
async def get_single_risk(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[CyberRiskResponse]:
    """Get a single quantified risk record."""
    record = CyberRiskQuantificationService.get_risk(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    return StandardResponse(data=CyberRiskQuantificationService.to_response(record))


@router.post("", response_model=StandardResponse[CyberRiskResponse], status_code=status.HTTP_201_CREATED)
async def create_risk(
    req: CreateRiskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[CyberRiskResponse]:
    """Create a new cyber risk record."""
    if req.scope_id:
        await check_scope_ownership(db, req.scope_id, current_user)

    record = await CyberRiskQuantificationService.create_or_sync_risk(
        title=req.title,
        description=req.description,
        scenario_type=req.scenario_type,
        frequency_label=req.frequency_label,
        impact_label=req.impact_label,
        exposure_value=req.exposure_value,
        scope_id=req.scope_id,
    )
    data = CyberRiskQuantificationService.to_response(record)
    return StandardResponse(data=data)


@router.post("/{id}/accept", response_model=StandardResponse[CyberRiskResponse])
async def accept_risk(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[CyberRiskResponse]:
    """Transition risk status to ACCEPTED."""
    record = CyberRiskQuantificationService.get_risk(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status == RiskQuantificationStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of a closed record",
        )

    res = CyberRiskQuantificationService.transition_status(id, RiskQuantificationStatus.ACCEPTED)
    return StandardResponse(data=CyberRiskQuantificationService.to_response(res))


@router.post("/{id}/mitigate", response_model=StandardResponse[CyberRiskResponse])
async def mitigate_risk(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[CyberRiskResponse]:
    """Transition risk status to MITIGATED."""
    record = CyberRiskQuantificationService.get_risk(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status == RiskQuantificationStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of a closed record",
        )

    res = CyberRiskQuantificationService.transition_status(id, RiskQuantificationStatus.MITIGATED)
    return StandardResponse(data=CyberRiskQuantificationService.to_response(res))


@router.post("/{id}/close", response_model=StandardResponse[CyberRiskResponse])
async def close_risk(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[CyberRiskResponse]:
    """Transition risk status to CLOSED."""
    record = CyberRiskQuantificationService.get_risk(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status == RiskQuantificationStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of a closed record",
        )

    res = CyberRiskQuantificationService.transition_status(id, RiskQuantificationStatus.CLOSED)
    return StandardResponse(data=CyberRiskQuantificationService.to_response(res))
