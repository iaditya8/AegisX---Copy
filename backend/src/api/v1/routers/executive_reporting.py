import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.user import StandardResponse
from src.domain.entities.executive_reporting import (
    ExecutiveReportStatus,
    ExecutiveSeverity,
    ScorecardStatus,
    ExecutiveReportResponse,
    ExecutiveScorecardResponse,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.executive_reporting_service import ExecutiveReportingService
from src.services.executive_history_service import ExecutiveHistoryService
from src.services.executive_scorecard_service import ExecutiveScorecardService
from src.services.executive_heatmap_service import ExecutiveHeatmapService
from src.services.executive_trend_service import ExecutiveTrendService
from src.services.executive_snapshot_service import ExecutiveSnapshotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/executive-reporting", tags=["executive-reporting"])


class CreateReportRequest(BaseModel):
    title: str
    description: str
    report_period: str
    report_type: str
    scope_id: Optional[uuid.UUID] = None
    included_entities: Optional[List[str]] = []


class TransitionStatusRequest(BaseModel):
    status: ExecutiveReportStatus


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

@router.get("", response_model=StandardResponse[List[ExecutiveReportResponse]])
async def list_reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[ExecutiveReportResponse]]:
    """List all executive reports, filtered by scope ownership."""
    reports = ExecutiveReportingService.get_all_reports()

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        reports = [r for r in reports if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [ExecutiveReportingService.to_response(r) for r in reports]
    return StandardResponse(data=data)


@router.get("/scorecard", response_model=StandardResponse[ExecutiveScorecardResponse])
async def get_scorecard(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[ExecutiveScorecardResponse]:
    """Retrieve dynamic executive scorecard health scorecard."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    else:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Non-admin users must specify scope_id",
            )
    card = ExecutiveScorecardService.calculate_scorecard(scope_id)
    return StandardResponse(data=card)


@router.get("/heatmap", response_model=StandardResponse[Dict])
async def get_heatmap(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict]:
    """Retrieve cyber risk heatmap coordinates."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    else:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Non-admin users must specify scope_id",
            )
    map_data = ExecutiveHeatmapService.generate_heatmap(scope_id)
    return StandardResponse(data=map_data)


@router.get("/trends", response_model=StandardResponse[Dict])
async def get_trends(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict]:
    """Retrieve historical trends."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    else:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Non-admin users must specify scope_id",
            )
    trends = ExecutiveTrendService.get_trends(scope_id)
    return StandardResponse(data=trends)


@router.get("/summary", response_model=StandardResponse[Dict])
async def get_summary_snapshot(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict]:
    """Rebuild and return the summary snapshot."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    else:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Non-admin users must specify scope_id",
            )
    snap = await ExecutiveSnapshotService.generate_snapshot(db, scope_id)
    return StandardResponse(data=snap)


@router.get("/{id}", response_model=StandardResponse[ExecutiveReportResponse])
async def get_report_details(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[ExecutiveReportResponse]:
    """Retrieve details of a specific executive report."""
    report = ExecutiveReportingService.get_report(id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    if report.scope_id:
        await check_scope_ownership(db, report.scope_id, current_user)

    data = ExecutiveReportingService.to_response(report)
    return StandardResponse(data=data)


@router.post("", response_model=StandardResponse[ExecutiveReportResponse], status_code=status.HTTP_201_CREATED)
async def create_report(
    req: CreateReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ExecutiveReportResponse]:
    """Manually create or synchronize an executive report."""
    if req.scope_id:
        await check_scope_ownership(db, req.scope_id, current_user)

    record = await ExecutiveReportingService.create_or_sync_report(
        title=req.title,
        description=req.description,
        report_period=req.report_period,
        report_type=req.report_type,
        scope_id=req.scope_id,
        included_entities=req.included_entities,
    )
    data = ExecutiveReportingService.to_response(record)
    return StandardResponse(data=data)


@router.post("/{id}/transition", response_model=StandardResponse[ExecutiveReportResponse])
async def transition_report_status(
    id: uuid.UUID,
    req: TransitionStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ExecutiveReportResponse]:
    """Transition report status safely, enforcing terminal state checks."""
    report = ExecutiveReportingService.get_report(id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    if report.scope_id:
        await check_scope_ownership(db, report.scope_id, current_user)

    if report.status == ExecutiveReportStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify status of an archived report",
        )

    record = ExecutiveReportingService.transition_report_status(id, req.status)
    data = ExecutiveReportingService.to_response(record)
    return StandardResponse(data=data)
