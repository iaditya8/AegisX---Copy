import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import Request

from src.core.security import create_access_token
from src.domain.entities.security_intelligence_graph import (
    NodeType,
    EdgeType,
    GraphComponentStatus,
    GraphNodeResponse,
    GraphEdgeResponse,
)
from src.infrastructure.database.models import User, Scope, Asset
from src.infrastructure.database.session import get_db
from src.services.security_intelligence_graph_service import SecurityIntelligenceGraphService
from src.services.graph_correlation_service import GraphCorrelationService
from src.services.graph_drift_service import GraphDriftService
from src.services.graph_snapshot_service import GraphSnapshotService
from src.services.graph_history_service import GraphHistoryService
from src.services.ai_context_builder import AIContextBuilder


ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SCOPE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
ALT_SCOPE_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")


@pytest.fixture(autouse=True)
def clean_graph_stores():
    SecurityIntelligenceGraphService.clear_graph()
    GraphDriftService.clear_drifts()
    GraphSnapshotService.clear_snapshots()


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_db():
    db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)
    db.get = AsyncMock()
    db.commit = AsyncMock()
    return db


# --- Graph Structure & Lifecycle Tests ---

def test_node_auto_creation():
    """Verify nodes can be synced/created dynamically and validates types."""
    node = SecurityIntelligenceGraphService.create_or_sync_node(
        node_type=NodeType.ASSET,
        entity_id=uuid.uuid4(),
        scope_id=SCOPE_ID,
    )
    assert node.node_type == NodeType.ASSET
    assert node.status == GraphComponentStatus.ACTIVE

    # Invalid Node Type
    with pytest.raises(ValueError):
        SecurityIntelligenceGraphService.create_or_sync_node(
            node_type="INVALID_TYPE",
            entity_id=uuid.uuid4(),
        )


def test_edge_auto_creation():
    """Verify edges can be synced/created dynamically and weights are registered."""
    source = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4())
    target = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.RISK, uuid.uuid4())

    edge = SecurityIntelligenceGraphService.create_or_sync_edge(
        source_id=source.node_id,
        target_id=target.node_id,
        edge_type=EdgeType.AFFECTS,
        weight=3.0,
        scope_id=SCOPE_ID,
    )
    assert edge.edge_type == EdgeType.AFFECTS
    assert edge.weight == 3.0
    assert edge.status == GraphComponentStatus.ACTIVE


def test_graph_fingerprint_stability():
    """Verify SHA-256 fingerprints are deterministic and stable across identical calls."""
    ent_id = uuid.uuid4()
    n1 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.COMPLIANCE, ent_id)
    n2 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.COMPLIANCE, ent_id)
    assert n1.node_fingerprint == n2.node_fingerprint
    assert n1.node_id == n2.node_id


def test_graph_identity_preservation():
    """Verify syncing identical components preserves the original node IDs and history."""
    ent_id = uuid.uuid4()
    node1 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.POSTURE, ent_id, SCOPE_ID)
    history1 = GraphHistoryService.get_history(node1.node_id)

    node2 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.POSTURE, ent_id, SCOPE_ID)

    assert node1.node_id == node2.node_id
    assert GraphHistoryService.get_history(node2.node_id) == history1


def test_graph_duplicate_prevention():
    """Verify that redundant sync calls do not add duplicate items to node/edge lists."""
    ent_id = uuid.uuid4()
    for _ in range(5):
        SecurityIntelligenceGraphService.create_or_sync_node(NodeType.KNOWLEDGE, ent_id, SCOPE_ID)
    
    nodes = SecurityIntelligenceGraphService.get_all_nodes()
    assert len(nodes) == 1


# --- Graph Terminal State Enforcement (DEPRECATED) ---

def test_graph_deprecation_transition():
    """Verify components transition to DEPRECATED terminal state and emit history."""
    node = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.INCIDENT, uuid.uuid4(), SCOPE_ID)
    SecurityIntelligenceGraphService.deprecate_node(node.node_id)
    assert node.status == GraphComponentStatus.DEPRECATED

    history = GraphHistoryService.get_history(node.node_id)
    event_types = [h.event_type for h in history]
    assert "DEPRECATED" in event_types


def test_graph_terminal_state_enforcement():
    """Verify that a deprecated component rejects updates or status transitions."""
    node = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.CASE, uuid.uuid4(), SCOPE_ID)
    SecurityIntelligenceGraphService.deprecate_node(node.node_id)

    # Re-syncing does not reactivate
    res = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.CASE, node.entity_id, SCOPE_ID)
    assert res.status == GraphComponentStatus.DEPRECATED


def test_deprecated_component_not_reactivated_by_sync():
    """Verify sync doesn't reactivate deprecated edges."""
    source = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4())
    target = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.RISK, uuid.uuid4())
    edge = SecurityIntelligenceGraphService.create_or_sync_edge(
        source_id=source.node_id, target_id=target.node_id, edge_type=EdgeType.AFFECTS, weight=3.0
    )
    SecurityIntelligenceGraphService.deprecate_edge(edge.edge_id)

    # Sync
    res = SecurityIntelligenceGraphService.create_or_sync_edge(
        source_id=source.node_id, target_id=target.node_id, edge_type=EdgeType.AFFECTS, weight=5.0
    )
    assert res.status == GraphComponentStatus.DEPRECATED
    assert res.weight == 3.0 # Weight not updated


@pytest.mark.asyncio
async def test_deprecated_component_not_reactivated_by_worker(mock_db):
    """Verify background worker refresh does not reactivate deprecated nodes or edges."""
    node = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4(), SCOPE_ID)
    SecurityIntelligenceGraphService.deprecate_node(node.node_id)

    # Mock database to return the same asset
    mock_asset = Asset(id=node.entity_id, scope_id=SCOPE_ID)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [mock_asset]
    mock_db.execute.return_value = mock_res

    await SecurityIntelligenceGraphService.rebuild_graph_topology(mock_db)
    assert node.status == GraphComponentStatus.DEPRECATED


@pytest.mark.asyncio
async def test_deprecated_component_not_reactivated_by_snapshot(mock_db):
    """Verify snapshot rebuild logic respects terminal deprecated states."""
    node = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.POSTURE, uuid.uuid4(), SCOPE_ID)
    SecurityIntelligenceGraphService.deprecate_node(node.node_id)

    snap = await GraphSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    assert snap["total_nodes"] == 0 # Deprecated node is not counted in active nodes


@pytest.mark.asyncio
async def test_deprecated_component_not_reactivated_by_drift(mock_db):
    """Verify drift updates ignore deprecated components and preserve terminal status."""
    node = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.RISK, uuid.uuid4(), SCOPE_ID)
    SecurityIntelligenceGraphService.deprecate_node(node.node_id)

    prev_snap = {"total_nodes": 1, "total_edges": 0, "average_weight": 0.0}
    await GraphDriftService.process_drift(mock_db, SCOPE_ID, prev_snap)

    assert node.status == GraphComponentStatus.DEPRECATED


# --- Immutable History preservation ---

def test_graph_history_preserved():
    """Verify graph components append history but never overwrite previous history."""
    node = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4(), SCOPE_ID)
    SecurityIntelligenceGraphService.deprecate_node(node.node_id)

    history = GraphHistoryService.get_history(node.node_id)
    assert len(history) == 2
    assert history[0].event_type == "NODE_ADDED"
    assert history[1].event_type == "DEPRECATED"


def test_graph_history_immutable():
    """Verify history entries returned are deep copies and cannot be modified by callers."""
    node = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4(), SCOPE_ID)
    history = GraphHistoryService.get_history(node.node_id)
    
    # Attempting to mutate history list (returned as a tuple) raises TypeError
    with pytest.raises(TypeError):
        history[0] = "MUTATED"


def test_graph_history_order_preserved():
    """Verify history log entries are sorted chronologically and retain exact sequences."""
    node = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4(), SCOPE_ID)
    SecurityIntelligenceGraphService.deprecate_node(node.node_id)

    history = GraphHistoryService.get_history(node.node_id)
    assert history[0].timestamp <= history[1].timestamp


# --- Cross-Domain Correlations & Pathfinding Traversals ---

def test_cross_domain_correlation_deterministic():
    """Verify that recalculate_cross_domain_links runs deterministically."""
    from src.services.case_service import CaseService, CaseRecord
    from src.services.incident_service import IncidentService, IncidentRecord
    from src.domain.entities.incident import IncidentSeverity, IncidentStatus
    
    IncidentService.clear_incidents()
    CaseService.clear_cases()

    # Pre-seed active Incident & Case
    inc_id = uuid.uuid4()
    case_id = uuid.uuid4()
    
    inc = IncidentRecord(
        incident_id=inc_id,
        incident_fingerprint="inc1",
        title="DDoS",
        description="Attack",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
    )
    IncidentService._incidents[inc_id] = inc

    from src.domain.entities.case import CaseSeverity, CaseStatus
    cs = CaseRecord(
        case_id=case_id,
        case_fingerprint="case1",
        title="Case A",
        description="Investigation Case",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
    )
    cs.incident_ids.append(inc_id)
    CaseService._cases[case_id] = cs

    # Assemble nodes
    SecurityIntelligenceGraphService.create_or_sync_node(NodeType.INCIDENT, inc_id, SCOPE_ID)
    SecurityIntelligenceGraphService.create_or_sync_node(NodeType.CASE, case_id, SCOPE_ID)

    GraphCorrelationService.recalculate_cross_domain_links()
    edges = SecurityIntelligenceGraphService.get_all_edges()

    assert len(edges) == 1
    assert edges[0].edge_type == EdgeType.CONTAINED_IN


def test_pathfinding_traversal_consistency():
    """Verify shortest path finding is consistent and returns correct nodes/weights."""
    n1 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4(), SCOPE_ID)
    n2 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.RISK, uuid.uuid4(), SCOPE_ID)
    n3 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.COMPLIANCE, uuid.uuid4(), SCOPE_ID)

    SecurityIntelligenceGraphService.create_or_sync_edge(n1.node_id, n2.node_id, EdgeType.AFFECTS, 2.0, SCOPE_ID)
    SecurityIntelligenceGraphService.create_or_sync_edge(n2.node_id, n3.node_id, EdgeType.MAPS_TO, 1.5, SCOPE_ID)

    path = SecurityIntelligenceGraphService.find_shortest_path(n1.node_id, n3.node_id)
    assert len(path) == 2
    assert path[0][0] == n1.node_id
    assert path[0][1] == n2.node_id
    assert path[1][0] == n2.node_id
    assert path[1][1] == n3.node_id


def test_centrality_metric_calculation():
    """Verify that degree centrality is computed accurately and deterministically."""
    n1 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4(), SCOPE_ID)
    n2 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.RISK, uuid.uuid4(), SCOPE_ID)
    SecurityIntelligenceGraphService.create_or_sync_edge(n1.node_id, n2.node_id, EdgeType.AFFECTS, 3.0, SCOPE_ID)

    centrality = SecurityIntelligenceGraphService.calculate_centrality()
    assert centrality[n1.node_id] == 3.0
    assert centrality[n2.node_id] == 3.0


# --- Graph Drift Detection ---

@pytest.mark.asyncio
async def test_graph_drift_detection(mock_db):
    """Verify structural drift logic detects node/edge count changes and weight changes."""
    n1 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4(), SCOPE_ID)
    n2 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.RISK, uuid.uuid4(), SCOPE_ID)
    SecurityIntelligenceGraphService.create_or_sync_edge(n1.node_id, n2.node_id, EdgeType.AFFECTS, 3.0, SCOPE_ID)

    prev_snap = {
        "total_nodes": 1,
        "total_edges": 0,
        "average_weight": 0.0,
    }

    await GraphDriftService.process_drift(mock_db, SCOPE_ID, prev_snap)
    drifts = GraphDriftService.get_drifts()

    assert len(drifts) == 1
    assert "Node count shifted" in drifts[0]["details"]


def test_graph_drift_clearing():
    """Verify graph drift logs can be cleared."""
    GraphDriftService._drifts.append({"test": "data"})
    GraphDriftService.clear_drifts()
    assert len(GraphDriftService.get_drifts()) == 0


# --- Snapshot Cache-Only Rebuild consistency ---

@pytest.mark.asyncio
async def test_snapshot_rebuild_consistency(mock_db):
    """Verify snapshot generation computes total nodes, edges, density, and average weights correctly."""
    n1 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4(), SCOPE_ID)
    n2 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.RISK, uuid.uuid4(), SCOPE_ID)
    SecurityIntelligenceGraphService.create_or_sync_edge(n1.node_id, n2.node_id, EdgeType.AFFECTS, 4.0, SCOPE_ID)

    snap = await GraphSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    assert snap["total_nodes"] == 2
    assert snap["total_edges"] == 1
    assert snap["average_weight"] == 4.0
    assert snap["density"] == 1.0


@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_deletion(mock_db):
    """Verify get_snapshot rebuilds from source graph if the cache is missing or deleted."""
    SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4(), SCOPE_ID)
    GraphSnapshotService.clear_snapshots()

    snap = await GraphSnapshotService.get_snapshot(mock_db, SCOPE_ID)
    assert snap["total_nodes"] == 1


@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_corruption(mock_db):
    """Verify snapshot rebuilds if cache exists but keys are corrupted/missing."""
    GraphSnapshotService._snapshots[SCOPE_ID] = {"corrupted": True}
    SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4(), SCOPE_ID)

    snap = await GraphSnapshotService.get_snapshot(mock_db, SCOPE_ID)
    assert "total_nodes" in snap
    assert snap["total_nodes"] == 1


@pytest.mark.asyncio
async def test_snapshot_not_authoritative(mock_db):
    """Verify snapshot doesn't store state exclusively; clearing snapshots doesn't delete graph nodes."""
    SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4(), SCOPE_ID)
    await GraphSnapshotService.generate_snapshot(mock_db, SCOPE_ID)

    GraphSnapshotService.clear_snapshots()
    assert len(SecurityIntelligenceGraphService.get_all_nodes()) == 1


# --- AI integration & Prompt Guardrails ---

@pytest.mark.asyncio
async def test_ai_context_graph_injection(mock_db):
    """Verify that build_asset_context includes graph_summary, graph_nodes, and graph_edges."""
    # Setup mock_db execution results
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def mock_get(model, ident):
        if model.__name__ == "Asset":
            a = Asset()
            a.id = ident
            a.scope_id = SCOPE_ID
            return a
        return None
    mock_db.get = AsyncMock(side_effect=mock_get)

    from src.services.asset_report_service import AssetReportService
    original_report = AssetReportService.generate_asset_report
    AssetReportService.generate_asset_report = AsyncMock(return_value={
        "asset": {"asset_id": str(uuid.uuid4()), "scope_id": str(SCOPE_ID)},
        "ports": [], "services": [], "technologies": [], "risk": {}, "findings": [], "exposure": {}
    })

    try:
        SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4(), SCOPE_ID)

        ctx = await AIContextBuilder.build_asset_context(mock_db, uuid.uuid4())
        assert "graph_summary" in ctx["asset"]
        assert "graph_nodes" in ctx
    finally:
        AssetReportService.generate_asset_report = original_report


def test_ai_advisory_only_enforcement():
    """Verify Copilot prompt builder restrains AI from mutating graph structures."""
    from src.services.ai_prompt_builder import AIPromptBuilder
    prompt = AIPromptBuilder.build_asset_prompt({"context": "empty"})
    assert "graph nodes, edges, path metrics, cross-domain correlations" in prompt


# --- Scope Isolation and RBAC Verification ---

@pytest.mark.asyncio
async def test_scope_isolation_for_graph_paths(mock_db):
    """Verify Dijkstra path requests enforce scope checks for non-admin users."""
    from fastapi.testclient import TestClient
    from src.main import app
    from src.api.v1.dependencies.auth import get_current_user

    n1 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.ASSET, uuid.uuid4(), SCOPE_ID)
    n2 = SecurityIntelligenceGraphService.create_or_sync_node(NodeType.RISK, uuid.uuid4(), SCOPE_ID)
    SecurityIntelligenceGraphService.create_or_sync_edge(n1.node_id, n2.node_id, EdgeType.AFFECTS, 2.0, SCOPE_ID)

    client = TestClient(app)

    operator_id = uuid.uuid4()
    headers = get_auth_header(operator_id, "operator")
    admin_headers = get_auth_header(ADMIN_ID, "admin")

    operator_user = User(id=operator_id, role="operator")
    admin_user = User(id=ADMIN_ID, role="admin")

    async def override_current_user(request: Request):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return operator_user
        token = auth.split(" ")[1]
        try:
            from src.core.security import decode_token
            payload = decode_token(token)
            roles = payload.get("roles", [])
            if "admin" in roles:
                return admin_user
        except Exception:
            pass
        return operator_user

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    
    async def override_db():
        db = MagicMock()
        db.execute = AsyncMock(return_value=mock_res)
        return db

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db

    try:
        resp = client.get(
            f"/api/v1/security-intelligence-graph/paths?source_node_id={n1.node_id}&target_node_id={n2.node_id}",
            headers=headers
        )
        assert resp.status_code == 403

        resp_admin = client.get(
            f"/api/v1/security-intelligence-graph/paths?source_node_id={n1.node_id}&target_node_id={n2.node_id}",
            headers=admin_headers
        )
        assert resp_admin.status_code == 200
    finally:
        app.dependency_overrides.clear()
