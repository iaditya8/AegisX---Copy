import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.security_decision import (
    DecisionType,
    DecisionStatus,
    DecisionResponse,
    DecisionSnapshotResponse,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.scope_service import get_scope_by_id
from src.services.security_decision_service import SecurityDecisionService
from src.services.decision_tradeoff_service import DecisionTradeoffService
from src.services.decision_drift_service import DecisionDriftService
from src.services.decision_snapshot_service import DecisionSnapshotService


router = APIRouter(prefix="/security-decision", tags=["security-decision"])


class DecisionCreateRequest(BaseModel):
    decision_type: DecisionType
    target_entity_id: uuid.UUID
    option_name: str
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

@router.post("/", response_model=DecisionResponse, status_code=status.HTTP_201_CREATED)
async def create_decision(
    req: DecisionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Create or sync a decision recommendation."""
    if req.scope_id:
        await check_scope_ownership(db, req.scope_id, current_user)

    decision = await SecurityDecisionService.create_or_sync_decision(
        decision_type=req.decision_type,
        target_entity_id=req.target_entity_id,
        option_name=req.option_name,
        scope_id=req.scope_id,
    )
    return decision


@router.post("/{id}/recommend", response_model=DecisionResponse)
async def recommend_decision(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition decision to RECOMMENDED status."""
    decision = SecurityDecisionService.get_decision(id)
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision with ID {id} not found",
        )

    if decision.scope_id:
        await check_scope_ownership(db, decision.scope_id, current_user)

    updated = await SecurityDecisionService.recommend_decision(id)
    return updated


@router.post("/{id}/commit", response_model=DecisionResponse)
async def commit_decision(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition decision to COMMITTED status."""
    decision = SecurityDecisionService.get_decision(id)
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision with ID {id} not found",
        )

    if decision.scope_id:
        await check_scope_ownership(db, decision.scope_id, current_user)

    updated = await SecurityDecisionService.commit_decision(id)
    return updated


@router.post("/{id}/archive", response_model=DecisionResponse)
async def archive_decision(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition decision to ARCHIVED status."""
    decision = SecurityDecisionService.get_decision(id)
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision with ID {id} not found",
        )

    if decision.scope_id:
        await check_scope_ownership(db, decision.scope_id, current_user)

    updated = await SecurityDecisionService.archive_decision(id)
    return updated


@router.get("/", response_model=List[DecisionResponse])
async def list_decisions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all decisions, filtered by allowed scopes for non-admins."""
    decisions = SecurityDecisionService.get_all_decisions()
    if current_user.role == "admin":
        return decisions

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    return [d for d in decisions if d.scope_id in allowed_scopes]


@router.get("/recommended", response_model=List[DecisionResponse])
async def list_recommended_decisions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all recommended decisions, filtered by allowed scopes."""
    decisions = SecurityDecisionService.get_all_decisions()
    filtered = [d for d in decisions if d.status == DecisionStatus.RECOMMENDED]
    if current_user.role == "admin":
        return filtered

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    return [d for d in filtered if d.scope_id in allowed_scopes]


@router.get("/committed", response_model=List[DecisionResponse])
async def list_committed_decisions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all committed decisions, filtered by allowed scopes."""
    decisions = SecurityDecisionService.get_all_decisions()
    filtered = [d for d in decisions if d.status == DecisionStatus.COMMITTED]
    if current_user.role == "admin":
        return filtered

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    return [d for d in filtered if d.scope_id in allowed_scopes]


@router.get("/drift")
async def list_drifts(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve decision drift logs."""
    return DecisionDriftService.get_drifts()


@router.get("/summary", response_model=DecisionSnapshotResponse)
async def get_summary(
    scope_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve the rebuildable decision snapshot summary for a scope."""
    await check_scope_ownership(db, scope_id, current_user)
    snap = await DecisionSnapshotService.get_snapshot(db, scope_id)
    return snap


@router.get("/{id}", response_model=DecisionResponse)
async def get_decision(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve a specific decision by ID."""
    decision = SecurityDecisionService.get_decision(id)
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision with ID {id} not found",
        )

    if decision.scope_id:
        await check_scope_ownership(db, decision.scope_id, current_user)

    return decision
