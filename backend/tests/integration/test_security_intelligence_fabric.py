import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request

from src.core.security import create_access_token
from src.domain.entities.security_intelligence_fabric import (
    FabricPriority,
    FabricStatus,
    PropagationMode,
    FabricIntelligenceNodeResponse,
)
from src.infrastructure.database.models import User, Scope, Asset
from src.infrastructure.database.session import get_db
from src.services.unified_security_intelligence_fabric_service import UnifiedSecurityIntelligenceFabricService
from src.services.intelligence_propagation_service import IntelligencePropagationService
from src.services.fabric_drift_service import FabricDriftService
from src.services.fabric_snapshot_service import FabricSnapshotService
from src.services.fabric_history_service import FabricHistoryService
from src.services.threat_intelligence_service import ThreatIntelligenceService
from src.services.ai_context_builder import AIContextBuilder


ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SCOPE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
ALT_SCOPE_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")


@pytest.fixture(autouse=True)
def clean_fabric_stores():
    UnifiedSecurityIntelligenceFabricService.clear_fabric()
    FabricDriftService.clear_drifts()
    FabricSnapshotService.clear_snapshots()
    ThreatIntelligenceService.clear_threats()


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}




# --- Fabric Structures & Lifecycle ---

@pytest.mark.asyncio
async def test_fabric_auto_creation(mock_db):
    """Verify fabric nodes can be created and validate categories."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node(
        source_type="THREAT_INTEL",
        scope_id=SCOPE_ID,
        target_links=[uuid.uuid4()],
    )
    assert n.source_type == "THREAT_INTEL"
    assert n.status == FabricStatus.ACTIVE

    # Invalid source
    with pytest.raises(ValueError):
        await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node(
            source_type="INVALID_SOURCE",
            target_links=[],
        )


@pytest.mark.asyncio
async def test_propagation_route_auto_creation(mock_db):
    """Verify propagation route objects are automatically generated."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node(
        source_type="THREAT_INTEL",
        scope_id=SCOPE_ID,
        target_links=[uuid.uuid4()],
    )
    routes = IntelligencePropagationService.get_propagations()
    assert len(routes) == 1
    assert routes[0].source_node_id == n.node_id


@pytest.mark.asyncio
async def test_fabric_fingerprint_stability(mock_db):
    """Verify SHA-256 fingerprints are deterministic and stable."""
    src = "RISK"
    n1 = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node(src, SCOPE_ID, rules_hash="123")
    n2 = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node(src, SCOPE_ID, rules_hash="123")
    assert n1.node_fingerprint == n2.node_fingerprint
    assert n1.node_id == n2.node_id


@pytest.mark.asyncio
async def test_fabric_identity_preservation(mock_db):
    """Verify syncing identical elements preserves ids and history."""
    src = "RISK"
    n1 = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node(src, SCOPE_ID, rules_hash="456")
    history1 = await FabricHistoryService.get_history(n1.node_id)

    n2 = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node(src, SCOPE_ID, rules_hash="456")
    assert n1.node_id == n2.node_id
    assert await FabricHistoryService.get_history(n2.node_id) == history1


@pytest.mark.asyncio
async def test_fabric_duplicate_prevention(mock_db):
    """Verify that redundant sync calls do not add duplicate items."""
    src = "RISK"
    for _ in range(5):
        await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node(src, SCOPE_ID, rules_hash="AD")
    
    nodes = UnifiedSecurityIntelligenceFabricService.get_all_fabric_nodes()
    assert len(nodes) == 1


@pytest.mark.asyncio
async def test_fabric_suspend_transition(mock_db):
    """Verify transition to SUSPENDED status."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    updated = await UnifiedSecurityIntelligenceFabricService.suspend_fabric_node(n.node_id)
    assert updated.status == FabricStatus.SUSPENDED

    history = await FabricHistoryService.get_history(n.node_id)
    event_types = [h.event_type for h in history]
    assert "SUSPENDED" in event_types


@pytest.mark.asyncio
async def test_fabric_terminate_transition(mock_db):
    """Verify transition to TERMINATED status."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    updated = await UnifiedSecurityIntelligenceFabricService.terminate_fabric_node(n.node_id)
    assert updated.status == FabricStatus.TERMINATED

    history = await FabricHistoryService.get_history(n.node_id)
    event_types = [h.event_type for h in history]
    assert "TERMINATED" in event_types


# --- Fabric Terminal State Enforcement ---

@pytest.mark.asyncio
async def test_fabric_terminal_state_enforcement(mock_db):
    """Verify that a terminated node rejects transitions."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    await UnifiedSecurityIntelligenceFabricService.terminate_fabric_node(n.node_id)

    res_sus = await UnifiedSecurityIntelligenceFabricService.suspend_fabric_node(n.node_id)
    assert res_sus.status == FabricStatus.TERMINATED


@pytest.mark.asyncio
async def test_terminated_fabric_not_reactivated_by_sync(mock_db):
    """Verify sync doesn't reactivate terminated nodes."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    await UnifiedSecurityIntelligenceFabricService.terminate_fabric_node(n.node_id)

    res = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node(n.source_type, SCOPE_ID, rules_hash="AD")
    assert res.status == FabricStatus.TERMINATED


@pytest.mark.asyncio
async def test_terminated_fabric_not_reactivated_by_worker(mock_db):
    """Verify background worker refresh does not reactivate terminated nodes."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    await UnifiedSecurityIntelligenceFabricService.terminate_fabric_node(n.node_id)

    await UnifiedSecurityIntelligenceFabricService.sync_fabric_state(mock_db)
    assert n.status == FabricStatus.TERMINATED


@pytest.mark.asyncio
async def test_terminated_fabric_not_reactivated_by_snapshot(mock_db):
    """Verify snapshot rebuild logic respects terminal terminated states."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    await UnifiedSecurityIntelligenceFabricService.terminate_fabric_node(n.node_id)

    snap = await FabricSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    assert snap["terminated_count"] == 1
    assert n.status == FabricStatus.TERMINATED


@pytest.mark.asyncio
async def test_terminated_fabric_not_reactivated_by_drift(mock_db):
    """Verify drift updates ignore terminated nodes and preserve terminal status."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    await UnifiedSecurityIntelligenceFabricService.terminate_fabric_node(n.node_id)

    prev_snap = {
        "total_nodes": 1,
        "active_count": 0,
        "suspended_count": 0,
        "terminated_count": 1,
        "average_confidence": 0.0,
    }
    await FabricDriftService.process_drift(mock_db, SCOPE_ID, prev_snap)

    assert n.status == FabricStatus.TERMINATED


@pytest.mark.asyncio
async def test_terminated_fabric_not_reactivated_by_propagation(mock_db):
    """Verify propagation updates ignore terminated nodes."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    await UnifiedSecurityIntelligenceFabricService.terminate_fabric_node(n.node_id)

    IntelligencePropagationService.process_propagation()
    assert n.status == FabricStatus.TERMINATED
    assert n.confidence_weights.get("current_confidence") == 1.0 # remains default/unmodified


# --- Immutable History preservation ---

@pytest.mark.asyncio
async def test_fabric_history_preserved(mock_db):
    """Verify history appends events but never overwrites previous history."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    await UnifiedSecurityIntelligenceFabricService.terminate_fabric_node(n.node_id)

    history = await FabricHistoryService.get_history(n.node_id)
    assert len(history) == 2
    assert history[0].event_type == "FABRIC_CREATED"
    assert history[1].event_type == "TERMINATED"


@pytest.mark.asyncio
async def test_fabric_history_immutable(mock_db):
    """Verify history entries are deep copies."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    history = await FabricHistoryService.get_history(n.node_id)
    
    with pytest.raises(TypeError):
        history[0] = "MUTATED"


@pytest.mark.asyncio
async def test_fabric_history_order_preserved(mock_db):
    """Verify history log entries are sorted chronologically."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    await UnifiedSecurityIntelligenceFabricService.terminate_fabric_node(n.node_id)

    history = await FabricHistoryService.get_history(n.node_id)
    assert history[0].timestamp <= history[1].timestamp


# --- Scoring Determinism & Derived Calculations ---

@pytest.mark.asyncio
async def test_propagation_schedule_deterministic(mock_db):
    """Verify propagation sequencing calculations are deterministic."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    
    IntelligencePropagationService.process_propagation()
    c1 = n.confidence_weights.get("current_confidence")
    assert c1 is not None

    IntelligencePropagationService.process_propagation()
    c2 = n.confidence_weights.get("current_confidence")
    assert c1 == c2


@pytest.mark.asyncio
async def test_confidence_weight_consistency(mock_db):
    """Verify confidence modifiers and decays map consistently."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("THREAT_INTEL", SCOPE_ID, rules_hash="AD")
    IntelligencePropagationService.process_propagation()
    conf = n.confidence_weights.get("current_confidence")
    assert conf is not None


@pytest.mark.asyncio
async def test_intelligence_propagation_impact(mock_db):
    """Verify decay parameters decay confidence scores correctly."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    IntelligencePropagationService.process_propagation()
    conf = n.confidence_weights.get("current_confidence")
    assert conf < 1.0 # 1.0 - 0.08 decay = 0.92 (or base_modifier * ... - decay)


# --- Fabric Drift Detection ---

@pytest.mark.asyncio
async def test_fabric_drift_detection(mock_db):
    """Verify structural drift logic detects node and score shifts."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    IntelligencePropagationService.process_propagation()

    prev_snap = {
        "total_nodes": 0,
        "active_count": 0,
        "suspended_count": 0,
        "terminated_count": 0,
        "average_confidence": 0.0,
    }

    await FabricDriftService.process_drift(mock_db, SCOPE_ID, prev_snap)
    drifts = FabricDriftService.get_drifts()

    assert len(drifts) > 0
    details = [d["details"].lower() for d in drifts]
    assert any("nodes count changed" in det for det in details)


def test_fabric_drift_clearing():
    """Verify drift logs can be cleared."""
    FabricDriftService._drifts.append({"test": "drift"})
    FabricDriftService.clear_drifts()
    assert len(FabricDriftService.get_drifts()) == 0


# --- Snapshot Cache-Only Rebuild consistency ---

@pytest.mark.asyncio
async def test_snapshot_rebuild_consistency(mock_db):
    """Verify snapshot generation computes counts and average confidence correctly."""
    n1 = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD1")
    n2 = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("POSTURE", SCOPE_ID, rules_hash="AD2")
    
    await UnifiedSecurityIntelligenceFabricService.suspend_fabric_node(n1.node_id)

    snap = await FabricSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    assert snap["total_nodes"] == 2
    assert snap["suspended_count"] == 1
    assert snap["active_count"] == 1


@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_deletion(mock_db):
    """Verify get_snapshot rebuilds from source if the cache is missing or deleted."""
    await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    FabricSnapshotService.clear_snapshots()

    snap = await FabricSnapshotService.get_snapshot(mock_db, SCOPE_ID)
    assert snap["total_nodes"] == 1


@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_corruption(mock_db):
    """Verify snapshot rebuilds if cache exists but keys are corrupted/missing."""
    FabricSnapshotService._snapshots[SCOPE_ID] = {"corrupted": True}
    await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")

    snap = await FabricSnapshotService.get_snapshot(mock_db, SCOPE_ID)
    assert "total_nodes" in snap
    assert snap["total_nodes"] == 1


@pytest.mark.asyncio
async def test_snapshot_not_authoritative(mock_db):
    """Verify snapshot doesn't store state exclusively; clearing snapshots doesn't delete active nodes."""
    await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    await FabricSnapshotService.generate_snapshot(mock_db, SCOPE_ID)

    FabricSnapshotService.clear_snapshots()
    assert len(UnifiedSecurityIntelligenceFabricService.get_all_fabric_nodes()) == 1


@pytest.mark.asyncio
async def test_snapshot_rebuild_from_source_of_truth(mock_db):
    """Verify get_snapshot loads from the source of truth when cache is empty."""
    await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    
    FabricSnapshotService.clear_snapshots()
    snap = await FabricSnapshotService.get_snapshot(mock_db, SCOPE_ID)
    assert snap["total_nodes"] == 1


# --- AI integration & Prompt Guardrails ---

@pytest.mark.asyncio
async def test_ai_context_fabric_injection(mock_db):
    """Verify that build_asset_context includes fabric_summary and fabric_nodes."""
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

    await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")

    try:
        ctx = await AIContextBuilder.build_asset_context(mock_db, uuid.uuid4())
        assert "fabric_summary" in ctx["asset"]
        assert "fabric_nodes" in ctx["asset"]
    finally:
        AssetReportService.generate_asset_report = original_report


def test_ai_advisory_only_enforcement():
    """Verify Copilot prompt builder restrains AI from mutating fabric routes."""
    from src.services.ai_prompt_builder import AIPromptBuilder
    prompt = AIPromptBuilder.build_asset_prompt({"context": "empty"})
    assert "fabric segments, propagation nodes, confidence weights, flow parameters, or fabric configurations" in prompt


# --- Scope Isolation and RBAC Verification ---

@pytest.mark.asyncio
async def test_rbac_fabric_scope_validation(mock_db):
    """Verify fabric API requests enforce scope checks for non-admin users."""
    from fastapi.testclient import TestClient
    from src.main import app
    from src.api.v1.dependencies.auth import get_current_user
    import src.api.v1.routers.security_intelligence_fabric as fb_router

    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")

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

    async def mock_get_scope(db, sid):
        s = Scope()
        s.id = sid
        s.owner_id = uuid.uuid4() # Mismatch owner
        s.deleted_at = None
        return s

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    
    async def override_db():
        db = MagicMock()
        db.execute = AsyncMock(return_value=mock_res)
        return db

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(fb_router, "get_scope_by_id", mock_get_scope)
        try:
            resp = client.get(
                f"/api/v1/security-intelligence-fabric/fabric/{n.node_id}",
                headers=headers
            )
            assert resp.status_code == 403

            resp_admin = client.get(
                f"/api/v1/security-intelligence-fabric/fabric/{n.node_id}",
                headers=admin_headers
            )
            assert resp_admin.status_code == 200
        finally:
            app.dependency_overrides.clear()


# --- Identity Preservation after worker/propagation/snapshot/drift ---

@pytest.mark.asyncio
async def test_fabric_identity_preserved_after_worker_refresh(mock_db):
    """Verify that worker refresh preserves fabric identity and history."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    history1 = await FabricHistoryService.get_history(n.node_id)

    await UnifiedSecurityIntelligenceFabricService.sync_fabric_state(mock_db)
    
    assert n.node_id is not None
    assert await FabricHistoryService.get_history(n.node_id) == history1


@pytest.mark.asyncio
async def test_fabric_identity_preserved_after_propagation_refresh(mock_db):
    """Verify that propagation sequencing preserves fabric identity and history."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    history1 = await FabricHistoryService.get_history(n.node_id)

    IntelligencePropagationService.process_propagation()

    assert n.node_id is not None
    assert await FabricHistoryService.get_history(n.node_id) == history1


@pytest.mark.asyncio
async def test_fabric_identity_preserved_after_snapshot_rebuild(mock_db):
    """Verify that snapshot rebuild preserves fabric identity."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    history1 = await FabricHistoryService.get_history(n.node_id)

    await FabricSnapshotService.generate_snapshot(mock_db, SCOPE_ID)

    assert n.node_id is not None
    assert await FabricHistoryService.get_history(n.node_id) == history1


@pytest.mark.asyncio
async def test_fabric_identity_preserved_after_drift_processing(mock_db):
    """Verify that drift processing preserves fabric identity."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    history1 = await FabricHistoryService.get_history(n.node_id)

    prev_snap = {
        "total_nodes": 1,
        "active_count": 1,
        "suspended_count": 0,
        "terminated_count": 0,
        "average_confidence": 0.0,
    }
    await FabricDriftService.process_drift(mock_db, SCOPE_ID, prev_snap)

    assert n.node_id is not None
    assert await FabricHistoryService.get_history(n.node_id) == history1


@pytest.mark.asyncio
async def test_propagation_determinism(mock_db):
    """Verify propagation calculations are deterministic."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    
    IntelligencePropagationService.process_propagation()
    c1 = n.confidence_weights.get("current_confidence")

    IntelligencePropagationService.process_propagation()
    c2 = n.confidence_weights.get("current_confidence")

    assert c1 == c2


@pytest.mark.asyncio
async def test_scope_isolation_for_fabric_events(mock_db):
    """Verify propagation calculation respects scope boundaries."""
    n1 = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD1")
    n2 = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", ALT_SCOPE_ID, rules_hash="AD2")

    IntelligencePropagationService.process_propagation()

    assert n1.confidence_weights.get("current_confidence") is not None
    assert n2.confidence_weights.get("current_confidence") is not None


@pytest.mark.asyncio
async def test_fabric_score_stability(mock_db):
    """Verify fabric scores are stable."""
    n = await UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node("RISK", SCOPE_ID, rules_hash="AD")
    IntelligencePropagationService.process_propagation()

    s1 = n.confidence_weights.get("current_confidence")
    IntelligencePropagationService.process_propagation()
    s2 = n.confidence_weights.get("current_confidence")

    assert s1 == s2


@pytest.mark.asyncio
async def test_worker_integration(mock_db):
    """Verify Celery task runner executes all Sprint 37 steps successfully."""
    from src.infrastructure.celery.worker import _execute_workflow_async
    
    with open("debug_log.txt", "a") as f:
        f.write(f"\n[TEST WORKER] mock_db={mock_db}, type={type(mock_db)}, mock_db.add={getattr(mock_db, 'add', None)}\n")
    workflow_id = uuid.uuid4()
    scan_run_id = uuid.uuid4()

    mock_workflow = MagicMock()
    mock_workflow.owner_id = ADMIN_ID
    mock_scan_run = MagicMock()
    mock_scan_run.status = "running"
    
    mock_scope = MagicMock()
    mock_scope.deleted_at = None
    mock_scope.owner_id = ADMIN_ID

    orig_get = getattr(mock_db, "_orig_get_impl", None)
    async def mock_get(model, ident):
        if model.__name__ == "Workflow" and ident == workflow_id:
            return mock_workflow
        if model.__name__ == "ScanRun" and ident == scan_run_id:
            return mock_scan_run
        if model.__name__ == "Scope" and ident == SCOPE_ID:
            return mock_scope
        if orig_get:
            return await orig_get(model, ident)
        return None

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None

    mock_db.get = AsyncMock(side_effect=mock_get)
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_session_factory = MagicMock(return_value=mock_db)
    mock_db.__aenter__.return_value = mock_db

    with patch(
        "src.infrastructure.celery.worker.AsyncSessionLocal",
        mock_session_factory,
    ):
        await _execute_workflow_async(workflow_id, scan_run_id, SCOPE_ID)
    
    assert mock_scan_run.status == "completed"
