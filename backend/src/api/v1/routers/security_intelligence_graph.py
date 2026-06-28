import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.security_intelligence_graph import (
    NodeType,
    EdgeType,
    GraphComponentStatus,
    GraphNodeResponse,
    GraphEdgeResponse,
    GraphPathResponse,
    GraphSnapshotResponse,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.scope_service import get_scope_by_id
from src.services.security_intelligence_graph_service import SecurityIntelligenceGraphService
from src.services.graph_correlation_service import GraphCorrelationService
from src.services.graph_drift_service import GraphDriftService
from src.services.graph_snapshot_service import GraphSnapshotService


router = APIRouter(prefix="/security-intelligence-graph", tags=["security-intelligence-graph"])


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


# --- Request Schemas ---

class CreateNodeRequest(BaseModel):
    node_type: NodeType
    entity_id: uuid.UUID
    scope_id: Optional[uuid.UUID] = None


class CreateEdgeRequest(BaseModel):
    source_id: uuid.UUID
    target_id: uuid.UUID
    edge_type: EdgeType
    weight: float
    scope_id: Optional[uuid.UUID] = None


# --- Endpoints ---

@router.post("/nodes", response_model=GraphNodeResponse, status_code=status.HTTP_201_CREATED)
async def create_node(
    req: CreateNodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Create or sync a new graph node."""
    if req.scope_id:
        await check_scope_ownership(db, req.scope_id, current_user)
    return SecurityIntelligenceGraphService.create_or_sync_node(
        node_type=req.node_type,
        entity_id=req.entity_id,
        scope_id=req.scope_id,
    )


@router.post("/edges", response_model=GraphEdgeResponse, status_code=status.HTTP_201_CREATED)
async def create_edge(
    req: CreateEdgeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Create or sync a new graph edge."""
    # Ensure source and target nodes exist
    source = SecurityIntelligenceGraphService.get_node(req.source_id)
    target = SecurityIntelligenceGraphService.get_node(req.target_id)
    if not source or not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source or target node not found in graph topology",
        )

    if req.scope_id:
        await check_scope_ownership(db, req.scope_id, current_user)

    return SecurityIntelligenceGraphService.create_or_sync_edge(
        source_id=req.source_id,
        target_id=req.target_id,
        edge_type=req.edge_type,
        weight=req.weight,
        scope_id=req.scope_id,
    )


@router.post("/components/{id}/deprecate", response_model=dict)
async def deprecate_component(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition a graph component (node or edge) to DEPRECATED terminal status."""
    # Check nodes
    node = SecurityIntelligenceGraphService.get_node(id)
    if node:
        if node.scope_id:
            await check_scope_ownership(db, node.scope_id, current_user)
        SecurityIntelligenceGraphService.deprecate_node(id)
        return {"status": "success", "message": f"Node {id} deprecated successfully."}

    # Check edges
    edge = SecurityIntelligenceGraphService.get_edge(id)
    if edge:
        if edge.scope_id:
            await check_scope_ownership(db, edge.scope_id, current_user)
        SecurityIntelligenceGraphService.deprecate_edge(id)
        return {"status": "success", "message": f"Edge {id} deprecated successfully."}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Component {id} not found",
    )


@router.get("/topology", response_model=dict)
async def get_topology(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all active nodes and edges in the graph."""
    nodes = SecurityIntelligenceGraphService.get_all_nodes()
    edges = SecurityIntelligenceGraphService.get_all_edges()

    active_nodes = [n for n in nodes if n.status != GraphComponentStatus.DEPRECATED]
    active_edges = [e for e in edges if e.status != GraphComponentStatus.DEPRECATED]

    if current_user.role == "admin":
        return {"nodes": active_nodes, "edges": active_edges}

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    filtered_nodes = [n for n in active_nodes if n.scope_id in allowed_scopes]
    filtered_edges = [e for e in active_edges if e.scope_id in allowed_scopes]

    return {"nodes": filtered_nodes, "edges": filtered_edges}


@router.get("/paths", response_model=GraphPathResponse)
async def get_path(
    source_node_id: uuid.UUID,
    target_node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Find deterministic shortest path between two nodes using Dijkstra algorithm."""
    source_node = SecurityIntelligenceGraphService.get_node(source_node_id)
    target_node = SecurityIntelligenceGraphService.get_node(target_node_id)

    if not source_node or not target_node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source or target node not found in graph topology",
        )

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        if source_node.scope_id not in allowed_scopes or target_node.scope_id not in allowed_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have access to source or target node scopes",
            )

    edges_tuples = SecurityIntelligenceGraphService.find_shortest_path(source_node_id, target_node_id)
    
    path_nodes = []
    path_edges = []
    total_cost = 0.0

    if edges_tuples:
        # Re-construct path node objects and edge objects
        visited_node_ids = {source_node_id, target_node_id}
        for u, v, etype, weight in edges_tuples:
            visited_node_ids.add(u)
            visited_node_ids.add(v)
            total_cost += weight
            
            # Find the actual edge object
            found_edge = None
            for edge in SecurityIntelligenceGraphService.get_all_edges():
                if edge.source_id == u and edge.target_id == v and edge.edge_type.value == etype:
                    found_edge = edge
                    break
            if found_edge:
                path_edges.append(found_edge)

        for nid in visited_node_ids:
            node_obj = SecurityIntelligenceGraphService.get_node(nid)
            if node_obj:
                path_nodes.append(node_obj)

    return GraphPathResponse(
        path_id=uuid.uuid4(),
        nodes=path_nodes,
        edges=path_edges,
        metrics={"cost": total_cost},
    )


@router.get("/correlations", response_model=List[GraphEdgeResponse])
async def list_correlations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all active graph correlation edges."""
    edges = SecurityIntelligenceGraphService.get_all_edges()
    active_correlations = [
        e for e in edges
        if e.edge_type == EdgeType.CORRELATES_WITH and e.status != GraphComponentStatus.DEPRECATED
    ]

    if current_user.role == "admin":
        return active_correlations

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    return [e for e in active_correlations if e.scope_id in allowed_scopes]


@router.get("/drift", response_model=List[dict])
async def get_drift(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve graph structural drift history logs."""
    drifts = GraphDriftService.get_drifts()
    if current_user.role == "admin":
        return drifts

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    return [d for d in drifts if d.get("scope_id") is None or uuid.UUID(d["scope_id"]) in allowed_scopes]


@router.get("/summary", response_model=dict)
async def get_summary(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve cached summary snapshot of the graph."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)

    if current_user.role != "admin" and not scope_id:
        # Fetch organization wide snapshot if user is admin, otherwise force scope snapshot
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Non-admin users must specify scope_id for graph summary",
        )

    return await GraphSnapshotService.get_snapshot(db, scope_id)
