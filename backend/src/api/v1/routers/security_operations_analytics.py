import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.user import StandardResponse
from src.domain.entities.security_operations_analytics import (
    AnalyticsStatus,
    AnalyticsResponse,
    AnalystPerformanceResponse,
    OperationalKPIResponse,
    OperationalKRIResponse,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.security_operations_analytics_service import SecurityOperationsAnalyticsService
from src.services.analytics_history_service import AnalyticsHistoryService
from src.services.analyst_performance_service import AnalystPerformanceService
from src.services.queue_analytics_service import QueueAnalyticsService
from src.services.operational_kpi_service import OperationalKPIService
from src.services.operational_kri_service import OperationalKRIService
from src.services.soc_snapshot_service import SOCSnapshotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/security-operations-analytics", tags=["security-operations-analytics"])


class CreateAnalyticsRequest(BaseModel):
    analytics_name: str
    description: str
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

@router.get("", response_model=StandardResponse[List[AnalyticsResponse]])
async def list_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[AnalyticsResponse]]:
    """List all security operations analytics records."""
    records = await SecurityOperationsAnalyticsService.get_all_analytics()

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [SecurityOperationsAnalyticsService.to_response(r) for r in records]
    return StandardResponse(data=data)


@router.get("/analytics/active", response_model=StandardResponse[List[AnalyticsResponse]])
async def get_active(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[AnalyticsResponse]]:
    """Get active security operations analytics records."""
    records = await SecurityOperationsAnalyticsService.get_all_analytics()
    records = [r for r in records if r.status == AnalyticsStatus.ACTIVE]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [SecurityOperationsAnalyticsService.to_response(r) for r in records]
    return StandardResponse(data=data)


@router.get("/analytics/archived", response_model=StandardResponse[List[AnalyticsResponse]])
async def get_archived(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[AnalyticsResponse]]:
    """Get archived security operations analytics records."""
    records = await SecurityOperationsAnalyticsService.get_all_analytics()
    records = [r for r in records if r.status == AnalyticsStatus.ARCHIVED]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [SecurityOperationsAnalyticsService.to_response(r) for r in records]
    return StandardResponse(data=data)


@router.get("/analytics/{id}", response_model=StandardResponse[AnalyticsResponse])
async def get_single_analytics(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[AnalyticsResponse]:
    """Get a single SOC analytics record."""
    record = await SecurityOperationsAnalyticsService.get_analytics(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analytics record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    return StandardResponse(data=SecurityOperationsAnalyticsService.to_response(record))


@router.get("/analysts", response_model=StandardResponse[List[AnalystPerformanceResponse]])
async def list_analysts(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[AnalystPerformanceResponse]]:
    """List all security analysts."""
    data = await AnalystPerformanceService.get_analysts()
    return StandardResponse(data=data)


@router.get("/analysts/rankings", response_model=StandardResponse[List[AnalystPerformanceResponse]])
async def get_rankings(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[AnalystPerformanceResponse]]:
    """Get analyst performance rankings."""
    data = await AnalystPerformanceService.get_rankings()
    return StandardResponse(data=data)


@router.get("/queues", response_model=StandardResponse[Dict])
async def get_queues(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict]:
    """Get SOC queue metrics."""
    data = QueueAnalyticsService.get_queue_summary()
    return StandardResponse(data=data)


@router.get("/queues/backlog", response_model=StandardResponse[Dict])
async def get_backlog(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict]:
    """Get SOC backlog metrics."""
    data = QueueAnalyticsService.get_queue_summary()
    return StandardResponse(data=data.get("backlog_metrics", {}))


@router.get("/kpis", response_model=StandardResponse[List[OperationalKPIResponse]])
async def get_kpis(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[OperationalKPIResponse]]:
    """Get SOC KPI metrics."""
    data = await OperationalKPIService.get_kpis()
    return StandardResponse(data=data)


@router.get("/kris", response_model=StandardResponse[List[OperationalKRIResponse]])
async def get_kris(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[OperationalKRIResponse]]:
    """Get SOC KRI metrics."""
    data = await OperationalKRIService.get_kris()
    return StandardResponse(data=data)


@router.get("/drift", response_model=StandardResponse[Dict])
async def get_drift(
    current_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[Dict]:
    """Retrieve SOC performance drift status logs."""
    return StandardResponse(data={"drift_logs": []})


@router.get("/summary", response_model=StandardResponse[Dict])
async def get_summary(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict]:
    """Get summary snapshot dashboard of SOC operations status."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    else:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Non-admin users must specify scope_id",
            )
    snap = await SOCSnapshotService.generate_snapshot(db, scope_id)
    return StandardResponse(data=snap)


@router.post("", response_model=StandardResponse[AnalyticsResponse], status_code=status.HTTP_201_CREATED)
async def create_analytics(
    req: CreateAnalyticsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[AnalyticsResponse]:
    """Create a new security operations analytics record."""
    if req.scope_id:
        await check_scope_ownership(db, req.scope_id, current_user)

    record = await SecurityOperationsAnalyticsService.create_or_sync_analytics(
        analytics_name=req.analytics_name,
        description=req.description,
        scope_id=req.scope_id,
    )
    data = SecurityOperationsAnalyticsService.to_response(record)
    return StandardResponse(data=data)


@router.post("/analytics/{id}/review", response_model=StandardResponse[AnalyticsResponse])
async def review_analytics(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[AnalyticsResponse]:
    """Transition record status to REVIEW."""
    record = await SecurityOperationsAnalyticsService.get_analytics(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analytics record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status == AnalyticsStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of an archived record",
        )

    res = await SecurityOperationsAnalyticsService.transition_status(id, AnalyticsStatus.REVIEW)
    return StandardResponse(data=SecurityOperationsAnalyticsService.to_response(res))


@router.post("/analytics/{id}/archive", response_model=StandardResponse[AnalyticsResponse])
async def archive_analytics(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[AnalyticsResponse]:
    """Transition record status to ARCHIVED."""
    record = await SecurityOperationsAnalyticsService.get_analytics(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analytics record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status == AnalyticsStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of an archived record",
        )

    res = await SecurityOperationsAnalyticsService.transition_status(id, AnalyticsStatus.ARCHIVED)
    return StandardResponse(data=SecurityOperationsAnalyticsService.to_response(res))
