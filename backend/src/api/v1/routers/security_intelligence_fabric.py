import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.security_intelligence_fabric import (
    FabricStatus,
    FabricIntelligenceNodeResponse,
    ConfidencePropagationResponse,
    FabricCorrelationResponse,
    FabricSnapshotResponse,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.scope_service import get_scope_by_id
from src.services.unified_security_intelligence_fabric_service import UnifiedSecurityIntelligenceFabricService
from src.services.intelligence_propagation_service import IntelligencePropagationService
from src.services.fabric_drift_service import FabricDriftService
from src.services.fabric_snapshot_service import FabricSnapshotService


router = APIRouter(prefix="/security-intelligence-fabric", tags=["security-intelligence-fabric"])


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

@router.post("/propagations", response_model=List[ConfidencePropagationResponse])
async def trigger_propagation(
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Trigger intelligence and confidence score propagation across all active domains."""
    IntelligencePropagationService.process_propagation()
    return IntelligencePropagationService.get_propagations()


@router.post("/score-maps", response_model=List[FabricCorrelationResponse])
async def calculate_score_maps(
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Trigger dynamic score map generation."""
    return IntelligencePropagationService.calculate_score_maps()


@router.post("/fabric/{id}/terminate", response_model=FabricIntelligenceNodeResponse)
async def terminate_fabric_node(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition fabric node status to TERMINATED (terminal state)."""
    node = UnifiedSecurityIntelligenceFabricService.get_fabric_node(id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fabric node with ID {id} not found",
        )

    if node.scope_id:
        await check_scope_ownership(db, node.scope_id, current_user)

    updated = await UnifiedSecurityIntelligenceFabricService.terminate_fabric_node(id)
    return updated


@router.get("/propagations", response_model=List[ConfidencePropagationResponse])
async def get_propagations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all active propagation routes, filtered by allowed scopes."""
    routes = IntelligencePropagationService.get_propagations()
    if current_user.role == "admin":
        return routes

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    # Filter propagation routes by allowed scopes of their source nodes
    filtered = []
    for r in routes:
        node = UnifiedSecurityIntelligenceFabricService.get_fabric_node(r.source_node_id)
        if node and node.scope_id in allowed_scopes:
            filtered.append(r)
    return filtered


@router.get("/score-maps", response_model=List[FabricCorrelationResponse])
async def get_score_maps(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all cross-domain score maps."""
    return IntelligencePropagationService.calculate_score_maps()


@router.get("/drift")
async def list_drifts(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve fabric drift logs."""
    return FabricDriftService.get_drifts()


@router.get("/summary", response_model=FabricSnapshotResponse)
async def get_summary(
    scope_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve the rebuildable fabric snapshot summary for a scope."""
    await check_scope_ownership(db, scope_id, current_user)
    snap = await FabricSnapshotService.get_snapshot(db, scope_id)
    return snap


@router.get("/fabric", response_model=List[FabricIntelligenceNodeResponse])
async def list_fabric_nodes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all fabric nodes, filtered by allowed scopes for non-admins."""
    nodes = UnifiedSecurityIntelligenceFabricService.get_all_fabric_nodes()
    if current_user.role == "admin":
        return nodes

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    return [n for n in nodes if n.scope_id in allowed_scopes]


@router.get("/fabric/{id}", response_model=FabricIntelligenceNodeResponse)
async def get_fabric_node(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve a specific fabric node by ID."""
    node = UnifiedSecurityIntelligenceFabricService.get_fabric_node(id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fabric node with ID {id} not found",
        )

    if node.scope_id:
        await check_scope_ownership(db, node.scope_id, current_user)

    return node
