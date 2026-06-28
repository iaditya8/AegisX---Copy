import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.autonomous_planning import (
    PlanPriority,
    PlanStatus,
    PlanningRecordResponse,
    PlanningSnapshotResponse,
    RoadmapResponse,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.scope_service import get_scope_by_id
from src.services.autonomous_security_planning_service import AutonomousSecurityPlanningService
from src.services.planning_optimization_service import PlanningOptimizationService
from src.services.planning_drift_service import PlanningDriftService
from src.services.planning_snapshot_service import PlanningSnapshotService


router = APIRouter(prefix="/autonomous-planning", tags=["autonomous-planning"])


class PlanCreateRequest(BaseModel):
    category: str
    name: str
    scope_id: Optional[uuid.UUID] = None
    priority: PlanPriority = PlanPriority.MEDIUM


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


# --- API Routes ---

@router.post("/", response_model=PlanningRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    req: PlanCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Create or sync a planning recommendation."""
    if req.scope_id:
        await check_scope_ownership(db, req.scope_id, current_user)

    plan = AutonomousSecurityPlanningService.create_or_sync_plan(
        category=req.category,
        name=req.name,
        scope_id=req.scope_id,
        priority=req.priority,
    )
    return plan


@router.post("/{id}/approve", response_model=PlanningRecordResponse)
async def approve_plan(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Approve the plan. Plan approvals must always be manually triggered by operators (API/UI)."""
    plan = AutonomousSecurityPlanningService.get_plan(id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan with ID {id} not found",
        )

    if plan.scope_id:
        await check_scope_ownership(db, plan.scope_id, current_user)

    updated = AutonomousSecurityPlanningService.approve_plan(id)
    return updated


@router.post("/{id}/activate", response_model=PlanningRecordResponse)
async def activate_plan(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition plan status to ACTIVE."""
    plan = AutonomousSecurityPlanningService.get_plan(id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan with ID {id} not found",
        )

    if plan.scope_id:
        await check_scope_ownership(db, plan.scope_id, current_user)

    updated = AutonomousSecurityPlanningService.activate_plan(id)
    return updated


@router.post("/{id}/close", response_model=PlanningRecordResponse)
async def close_plan(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition plan status to CLOSED."""
    plan = AutonomousSecurityPlanningService.get_plan(id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan with ID {id} not found",
        )

    if plan.scope_id:
        await check_scope_ownership(db, plan.scope_id, current_user)

    updated = AutonomousSecurityPlanningService.close_plan(id)
    return updated


@router.get("/", response_model=List[PlanningRecordResponse])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all plans, filtered by allowed scopes for non-admins."""
    plans = AutonomousSecurityPlanningService.get_all_plans()
    if current_user.role == "admin":
        return plans

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    return [p for p in plans if p.scope_id in allowed_scopes]


@router.get("/active", response_model=List[PlanningRecordResponse])
async def list_active_plans(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all active plans, filtered by allowed scopes."""
    plans = AutonomousSecurityPlanningService.get_all_plans()
    filtered = [p for p in plans if p.status == PlanStatus.ACTIVE]
    if current_user.role == "admin":
        return filtered

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    return [p for p in filtered if p.scope_id in allowed_scopes]


@router.get("/roadmaps", response_model=List[RoadmapResponse])
async def list_roadmaps(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all plan roadmaps, filtered by allowed scopes."""
    plans = AutonomousSecurityPlanningService.get_all_plans()
    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        plans = [p for p in plans if p.scope_id in allowed_scopes]

    roadmaps = []
    for p in plans:
        if p.roadmap:
            roadmaps.append(p.roadmap)
    return roadmaps


@router.get("/drift")
async def list_drifts(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve planning drift logs."""
    return PlanningDriftService.get_drifts()


@router.get("/summary", response_model=PlanningSnapshotResponse)
async def get_summary(
    scope_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve the rebuildable planning snapshot summary for a scope."""
    await check_scope_ownership(db, scope_id, current_user)
    snap = await PlanningSnapshotService.get_snapshot(db, scope_id)
    return snap


@router.get("/{id}", response_model=PlanningRecordResponse)
async def get_plan(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve a specific plan by ID."""
    plan = AutonomousSecurityPlanningService.get_plan(id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan with ID {id} not found",
        )

    if plan.scope_id:
        await check_scope_ownership(db, plan.scope_id, current_user)

    return plan
