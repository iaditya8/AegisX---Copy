import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.hunt import (
    HuntResponse,
    HuntSeverity,
    HuntStatus,
    HuntType,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.hunt_service import HuntService, HuntRecord
from src.services.hunt_snapshot_service import HuntSnapshotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/threat-hunting", tags=["threat-hunting"])


class CreateHuntRequest(BaseModel):
    title: str
    description: str
    hunt_type: HuntType
    severity: HuntSeverity
    scope_id: Optional[uuid.UUID] = None
    owner_id: Optional[uuid.UUID] = None
    related_entities: Optional[List[dict]] = None


# --- Helper Checks ---

async def check_scope_ownership(
    db: AsyncSession, scope_id: uuid.UUID, current_user: User
) -> None:
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
    if current_user.role == "admin":
        return set()

    q_scopes = select(Scope).where(
        Scope.owner_id == current_user.id, Scope.deleted_at.is_(None)
    )
    res_scopes = await db.execute(q_scopes)
    scopes = res_scopes.scalars().all()
    return {s.id for s in scopes}


# --- Endpoints ---

@router.get("/hunts", response_model=List[HuntResponse])
async def list_hunts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """List threat hunts, filtered by scope ownership."""
    hunts = HuntService.get_all_hunts()
    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        hunts = [h for h in hunts if h.scope_id is None or h.scope_id in allowed_scopes]

    return [HuntService.to_response(h) for h in hunts]


@router.get("/hunts/metrics")
async def get_hunt_metrics(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve hunt metrics and snapshots."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    elif current_user.role != "admin":
        # If no scope_id is provided and the user is not admin, they are not allowed to query global metrics
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Non-admin users must specify a scope they own",
        )

    snapshot = HuntSnapshotService.get_snapshot(scope_id)
    return snapshot


@router.get("/hunts/{hunt_id}", response_model=HuntResponse)
async def get_hunt(
    hunt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Get hunt details by ID, validating scope ownership."""
    hunt = HuntService.get_hunt(hunt_id)
    if not hunt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hunt not found",
        )

    if hunt.scope_id:
        await check_scope_ownership(db, hunt.scope_id, current_user)
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Access to global hunts requires admin role",
        )

    return HuntService.to_response(hunt)


@router.post("/hunts", response_model=HuntResponse, status_code=status.HTTP_201_CREATED)
async def create_or_sync_hunt(
    req: CreateHuntRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Create or sync a hunt."""
    if req.scope_id:
        await check_scope_ownership(db, req.scope_id, current_user)
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Access to global scope requires admin role",
        )

    try:
        hunt = HuntService.create_or_sync_hunt(
            title=req.title,
            description=req.description,
            hunt_type=req.hunt_type,
            severity=req.severity,
            scope_id=req.scope_id,
            owner_id=req.owner_id,
            related_entities=req.related_entities,
        )
        return HuntService.to_response(hunt)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/hunts/{hunt_id}/activate", response_model=HuntResponse)
async def activate_hunt(
    hunt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition hunt to ACTIVE status."""
    hunt = HuntService.get_hunt(hunt_id)
    if not hunt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hunt not found",
        )

    if hunt.scope_id:
        await check_scope_ownership(db, hunt.scope_id, current_user)
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin role required for global hunts",
        )

    try:
        activated = HuntService.activate_hunt(hunt_id, user_id=current_user.id)
        # Force snapshot rebuild
        HuntSnapshotService.generate_snapshot(hunt.scope_id)
        return HuntService.to_response(activated)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/hunts/{hunt_id}/review", response_model=HuntResponse)
async def review_hunt(
    hunt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition hunt to UNDER_REVIEW status."""
    hunt = HuntService.get_hunt(hunt_id)
    if not hunt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hunt not found",
        )

    if hunt.scope_id:
        await check_scope_ownership(db, hunt.scope_id, current_user)
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin role required for global hunts",
        )

    try:
        reviewed = HuntService.review_hunt(hunt_id)
        HuntSnapshotService.generate_snapshot(hunt.scope_id)
        return HuntService.to_response(reviewed)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/hunts/{hunt_id}/complete", response_model=HuntResponse)
async def complete_hunt(
    hunt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition hunt to COMPLETED status."""
    hunt = HuntService.get_hunt(hunt_id)
    if not hunt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hunt not found",
        )

    if hunt.scope_id:
        await check_scope_ownership(db, hunt.scope_id, current_user)
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin role required for global hunts",
        )

    try:
        completed = HuntService.complete_hunt(hunt_id)
        HuntSnapshotService.generate_snapshot(hunt.scope_id)
        return HuntService.to_response(completed)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/hunts/{hunt_id}/close", response_model=HuntResponse)
async def close_hunt(
    hunt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition hunt to CLOSED status (terminal state)."""
    hunt = HuntService.get_hunt(hunt_id)
    if not hunt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hunt not found",
        )

    if hunt.scope_id:
        await check_scope_ownership(db, hunt.scope_id, current_user)
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin role required for global hunts",
        )

    try:
        closed = HuntService.close_hunt(hunt_id)
        HuntSnapshotService.generate_snapshot(hunt.scope_id)
        return HuntService.to_response(closed)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/hunts/{hunt_id}/escalate", response_model=HuntResponse)
async def escalate_hunt(
    hunt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition hunt to ESCALATED status."""
    hunt = HuntService.get_hunt(hunt_id)
    if not hunt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hunt not found",
        )

    if hunt.scope_id:
        await check_scope_ownership(db, hunt.scope_id, current_user)
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin role required for global hunts",
        )

    try:
        escalated = HuntService.escalate_hunt(hunt_id)
        HuntSnapshotService.generate_snapshot(hunt.scope_id)
        return HuntService.to_response(escalated)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
