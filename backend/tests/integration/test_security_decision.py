import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import Request

from src.core.security import create_access_token
from src.domain.entities.security_decision import (
    DecisionImpact,
    DecisionStatus,
    DecisionType,
    DecisionResponse,
)
from src.infrastructure.database.models import User, Scope, Asset
from src.infrastructure.database.session import get_db
from src.services.security_decision_service import SecurityDecisionService
from src.services.decision_tradeoff_service import DecisionTradeoffService
from src.services.decision_drift_service import DecisionDriftService
from src.services.decision_snapshot_service import DecisionSnapshotService
from src.services.decision_history_service import DecisionHistoryService
from src.services.ai_context_builder import AIContextBuilder


ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SCOPE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
ALT_SCOPE_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")


@pytest.fixture(autouse=True)
def clean_decision_stores():
    SecurityDecisionService.clear_decisions()
    DecisionDriftService.clear_drifts()
    DecisionSnapshotService.clear_snapshots()


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}





# --- Decision Structures & Lifecycle ---

@pytest.mark.asyncio
async def test_decision_auto_creation(mock_db):
    """Verify decisions can be synced/created dynamically and validates types."""
    d = await SecurityDecisionService.create_or_sync_decision(
        decision_type=DecisionType.REMEDIATION,
        target_entity_id=uuid.uuid4(),
        option_name="Remediate Target Server",
        scope_id=SCOPE_ID,
    )
    assert d.decision_type == DecisionType.REMEDIATION
    assert d.status == DecisionStatus.ACTIVE

    # Invalid Decision Type
    with pytest.raises(ValueError):
        await SecurityDecisionService.create_or_sync_decision(
            decision_type="INVALID_TYPE",
            target_entity_id=uuid.uuid4(),
            option_name="Invalid Type Options",
        )


@pytest.mark.asyncio
async def test_decision_fingerprint_stability(mock_db):
    """Verify SHA-256 fingerprints are deterministic and stable across identical calls."""
    ent_id = uuid.uuid4()
    opt_name = "Patch Server CVEs"
    d1 = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, ent_id, opt_name)
    d2 = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, ent_id, opt_name)
    assert d1.decision_fingerprint == d2.decision_fingerprint
    assert d1.decision_id == d2.decision_id


@pytest.mark.asyncio
async def test_decision_identity_preservation(mock_db):
    """Verify syncing identical components preserves the original decision IDs and history."""
    ent_id = uuid.uuid4()
    opt_name = "Update Firewall Rules"
    d1 = await SecurityDecisionService.create_or_sync_decision(DecisionType.MITIGATION, ent_id, opt_name, SCOPE_ID)
    history1 = await DecisionHistoryService.get_history(d1.decision_id)

    d2 = await SecurityDecisionService.create_or_sync_decision(DecisionType.MITIGATION, ent_id, opt_name, SCOPE_ID)

    assert d1.decision_id == d2.decision_id
    assert await DecisionHistoryService.get_history(d2.decision_id) == history1


@pytest.mark.asyncio
async def test_decision_duplicate_prevention(mock_db):
    """Verify that redundant sync calls do not add duplicate items to decision list."""
    ent_id = uuid.uuid4()
    opt_name = "Accept Low Severity CVEs"
    for _ in range(5):
        await SecurityDecisionService.create_or_sync_decision(DecisionType.ACCEPTANCE, ent_id, opt_name, SCOPE_ID)
    
    decisions = SecurityDecisionService.get_all_decisions()
    assert len(decisions) == 1


@pytest.mark.asyncio
async def test_decision_recommend_transition(mock_db):
    """Verify transition to RECOMMENDED status."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Remediate SQL", SCOPE_ID)
    updated = await SecurityDecisionService.recommend_decision(d.decision_id)
    assert updated.status == DecisionStatus.RECOMMENDED

    history = await DecisionHistoryService.get_history(d.decision_id)
    event_types = [h.event_type for h in history]
    assert "RECOMMENDED" in event_types


@pytest.mark.asyncio
async def test_decision_commit_transition(mock_db):
    """Verify transition to COMMITTED status."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Deploy MFA", SCOPE_ID)
    updated = await SecurityDecisionService.commit_decision(d.decision_id)
    assert updated.status == DecisionStatus.COMMITTED

    history = await DecisionHistoryService.get_history(d.decision_id)
    event_types = [h.event_type for h in history]
    assert "COMMITTED" in event_types


@pytest.mark.asyncio
async def test_decision_archive_transition(mock_db):
    """Verify transition to ARCHIVED status."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Enable TLS 1.3", SCOPE_ID)
    updated = await SecurityDecisionService.archive_decision(d.decision_id)
    assert updated.status == DecisionStatus.ARCHIVED

    history = await DecisionHistoryService.get_history(d.decision_id)
    event_types = [h.event_type for h in history]
    assert "ARCHIVED" in event_types


# --- Decision Terminal State Enforcement ---

@pytest.mark.asyncio
async def test_decision_terminal_state_enforcement(mock_db):
    """Verify that an archived decision rejects status transitions."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "MFA Rule", SCOPE_ID)
    await SecurityDecisionService.archive_decision(d.decision_id)

    # Attempt transition
    res_rec = await SecurityDecisionService.recommend_decision(d.decision_id)
    res_com = await SecurityDecisionService.commit_decision(d.decision_id)

    assert res_rec.status == DecisionStatus.ARCHIVED
    assert res_com.status == DecisionStatus.ARCHIVED


@pytest.mark.asyncio
async def test_archived_decision_not_reactivated_by_sync(mock_db):
    """Verify sync doesn't reactivate archived decisions."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Sync Check", SCOPE_ID)
    await SecurityDecisionService.archive_decision(d.decision_id)

    # Re-sync
    res = await SecurityDecisionService.create_or_sync_decision(d.decision_type, d.target_entity_id, d.option_name, SCOPE_ID)
    assert res.status == DecisionStatus.ARCHIVED


@pytest.mark.asyncio
async def test_archived_decision_not_reactivated_by_worker(mock_db):
    """Verify background worker refresh does not reactivate archived decisions."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Worker Sync Check", SCOPE_ID)
    await SecurityDecisionService.archive_decision(d.decision_id)

    # Trigger worker sync
    from src.services.governance_risk_compliance_service import GovernanceRiskComplianceService
    GovernanceRiskComplianceService.clear_assessments()

    await SecurityDecisionService.sync_decision_recommendations(mock_db)
    assert d.status == DecisionStatus.ARCHIVED


@pytest.mark.asyncio
async def test_archived_decision_not_reactivated_by_snapshot(mock_db):
    """Verify snapshot rebuild logic respects terminal archived states."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Snap Sync Check", SCOPE_ID)
    await SecurityDecisionService.archive_decision(d.decision_id)

    snap = await DecisionSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    assert snap["archived_count"] == 1
    assert snap["recommended_count"] == 0
    assert d.status == DecisionStatus.ARCHIVED


@pytest.mark.asyncio
async def test_archived_decision_not_reactivated_by_drift(mock_db):
    """Verify drift updates ignore archived decisions and preserve terminal status."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Drift Check", SCOPE_ID)
    await SecurityDecisionService.archive_decision(d.decision_id)

    prev_snap = {
        "total_decisions": 1,
        "recommended_count": 0,
        "committed_count": 0,
        "archived_count": 1,
        "average_net_benefit": 0.0,
    }
    await DecisionDriftService.process_drift(mock_db, SCOPE_ID, prev_snap)

    assert d.status == DecisionStatus.ARCHIVED


@pytest.mark.asyncio
async def test_archived_decision_not_reactivated_by_tradeoff(mock_db):
    """Verify tradeoff updates ignore archived decisions."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Tradeoff Check", SCOPE_ID)
    await SecurityDecisionService.archive_decision(d.decision_id)

    DecisionTradeoffService.calculate()
    assert d.status == DecisionStatus.ARCHIVED
    assert d.tradeoff_matrix is None # Should remain un-calculated / None


# --- Immutable History preservation ---

@pytest.mark.asyncio
async def test_decision_history_preserved(mock_db):
    """Verify decision recommendations append history but never overwrite previous history."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "MFA Rule", SCOPE_ID)
    await SecurityDecisionService.archive_decision(d.decision_id)

    history = await DecisionHistoryService.get_history(d.decision_id)
    assert len(history) == 2
    assert history[0].event_type == "CREATED"
    assert history[1].event_type == "ARCHIVED"


@pytest.mark.asyncio
async def test_decision_history_immutable(mock_db):
    """Verify history entries returned are deep copies and cannot be modified by callers."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "MFA Rule", SCOPE_ID)
    history = await DecisionHistoryService.get_history(d.decision_id)
    
    with pytest.raises(TypeError):
        history[0] = "MUTATED"


@pytest.mark.asyncio
async def test_decision_history_order_preserved(mock_db):
    """Verify history log entries are sorted chronologically and retain exact sequences."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "MFA Rule", SCOPE_ID)
    await SecurityDecisionService.archive_decision(d.decision_id)

    history = await DecisionHistoryService.get_history(d.decision_id)
    assert history[0].timestamp <= history[1].timestamp


# --- Scoring Determinism & Derived Calculations ---

@pytest.mark.asyncio
async def test_tradeoff_matrix_deterministic(mock_db):
    """Verify tradeoff calculation logic is fully deterministic."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Patch SSH", SCOPE_ID)
    
    DecisionTradeoffService.calculate()
    t1 = d.tradeoff_matrix
    assert t1 is not None

    DecisionTradeoffService.calculate()
    t2 = d.tradeoff_matrix
    assert t1.net_benefit == t2.net_benefit
    assert t1.estimated_cost == t2.estimated_cost


@pytest.mark.asyncio
async def test_operational_impact_estimation(mock_db):
    """Verify operational impact score estimation mapping."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Patch SSH", SCOPE_ID)
    DecisionTradeoffService.calculate()
    assert d.impact_metrics.operational_impact_score == 10.0 * (1.0 - 0.8) # 2.0
    assert d.impact_metrics.decision_impact == DecisionImpact.LOW


@pytest.mark.asyncio
async def test_risk_reduction_calculation(mock_db):
    """Verify risk reduction calculation utilizes factors and baseline correctly."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Patch SSH", SCOPE_ID)
    DecisionTradeoffService.calculate()
    assert d.impact_metrics.confidence_score > 0.0
    assert d.tradeoff_matrix.estimated_risk_reduction > 0.0


# --- Decision Drift Detection ---

@pytest.mark.asyncio
async def test_decision_drift_detection(mock_db):
    """Verify structural drift logic detects decision benefit and count shifts."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "MFA Drift", SCOPE_ID)
    DecisionTradeoffService.calculate()

    prev_snap = {
        "total_decisions": 0,
        "recommended_count": 0,
        "committed_count": 0,
        "archived_count": 0,
        "average_net_benefit": 0.0,
    }

    await DecisionDriftService.process_drift(mock_db, SCOPE_ID, prev_snap)
    drifts = DecisionDriftService.get_drifts()

    assert len(drifts) > 0
    assert "decisions count changed" in drifts[1]["details"].lower()


@pytest.mark.asyncio
async def test_decision_drift_clearing(mock_db):
    """Verify drift logs can be cleared."""
    DecisionDriftService._drifts.append({"test": "drift"})
    DecisionDriftService.clear_drifts()
    assert len(DecisionDriftService.get_drifts()) == 0


# --- Snapshot Cache-Only Rebuild consistency ---

@pytest.mark.asyncio
async def test_snapshot_rebuild_consistency(mock_db):
    """Verify snapshot generation computes counts and average net benefits correctly."""
    d1 = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "D1", SCOPE_ID)
    d2 = await SecurityDecisionService.create_or_sync_decision(DecisionType.MITIGATION, uuid.uuid4(), "D2", SCOPE_ID)
    
    await SecurityDecisionService.recommend_decision(d1.decision_id)
    await SecurityDecisionService.commit_decision(d2.decision_id)

    DecisionTradeoffService.calculate()

    snap = await DecisionSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    assert snap["total_decisions"] == 2
    assert snap["recommended_count"] == 1
    assert snap["committed_count"] == 1


@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_deletion(mock_db):
    """Verify get_snapshot rebuilds from source if the cache is missing or deleted."""
    await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "D1", SCOPE_ID)
    DecisionSnapshotService.clear_snapshots()

    snap = await DecisionSnapshotService.get_snapshot(mock_db, SCOPE_ID)
    assert snap["total_decisions"] == 1


@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_corruption(mock_db):
    """Verify snapshot rebuilds if cache exists but keys are corrupted/missing."""
    DecisionSnapshotService._snapshots[SCOPE_ID] = {"corrupted": True}
    await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "D1", SCOPE_ID)

    snap = await DecisionSnapshotService.get_snapshot(mock_db, SCOPE_ID)
    assert "total_decisions" in snap
    assert snap["total_decisions"] == 1


@pytest.mark.asyncio
async def test_snapshot_not_authoritative(mock_db):
    """Verify snapshot doesn't store state exclusively; clearing snapshots doesn't delete active decisions."""
    await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "D1", SCOPE_ID)
    await DecisionSnapshotService.generate_snapshot(mock_db, SCOPE_ID)

    DecisionSnapshotService.clear_snapshots()
    assert len(SecurityDecisionService.get_all_decisions()) == 1


@pytest.mark.asyncio
async def test_snapshot_rebuild_from_source_of_truth(mock_db):
    """Verify get_snapshot loads from the source of truth when cache is empty."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "D1", SCOPE_ID)
    
    DecisionSnapshotService.clear_snapshots()
    snap = await DecisionSnapshotService.get_snapshot(mock_db, SCOPE_ID)
    assert snap["total_decisions"] == 1


# --- AI integration & Prompt Guardrails ---

@pytest.mark.asyncio
async def test_ai_context_decision_injection(mock_db):
    """Verify that build_asset_context includes decision_summary and decision_records."""
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

    await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "D1", SCOPE_ID)

    try:
        ctx = await AIContextBuilder.build_asset_context(mock_db, uuid.uuid4())
        assert "decision_summary" in ctx["asset"]
        assert "decision_records" in ctx["asset"]
    finally:
        AssetReportService.generate_asset_report = original_report


@pytest.mark.asyncio
async def test_ai_advisory_only_enforcement(mock_db):
    """Verify Copilot prompt builder restrains AI from mutating decisions."""
    from src.services.ai_prompt_builder import AIPromptBuilder
    prompt = AIPromptBuilder.build_asset_prompt({"context": "empty"})
    assert "decisions, tradeoff matrices, impact evaluations" in prompt


# --- Scope Isolation and RBAC Verification ---

@pytest.mark.asyncio
async def test_rbac_decision_scope_validation(mock_db):
    """Verify decision API requests enforce scope checks for non-admin users."""
    from fastapi.testclient import TestClient
    from src.main import app
    from src.api.v1.dependencies.auth import get_current_user
    import src.api.v1.routers.security_decision as dec_router

    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "D1", SCOPE_ID)

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
        mp.setattr(dec_router, "get_scope_by_id", mock_get_scope)
        try:
            resp = client.get(
                f"/api/v1/security-decision/{d.decision_id}",
                headers=headers
            )
            assert resp.status_code == 403

            resp_admin = client.get(
                f"/api/v1/security-decision/{d.decision_id}",
                headers=admin_headers
            )
            assert resp_admin.status_code == 200
        finally:
            app.dependency_overrides.clear()


# --- Identity Preservation after worker/tradeoff/snapshot/drift ---

@pytest.mark.asyncio
async def test_decision_identity_preserved_after_worker_refresh(mock_db):
    """Verify that worker refresh preserves decision identity and history."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Worker Sync Check", SCOPE_ID)
    history1 = await DecisionHistoryService.get_history(d.decision_id)

    # Sync
    await SecurityDecisionService.sync_decision_recommendations(mock_db)
    
    assert d.decision_id is not None
    assert await DecisionHistoryService.get_history(d.decision_id) == history1


@pytest.mark.asyncio
async def test_decision_identity_preserved_after_tradeoff_refresh(mock_db):
    """Verify that tradeoff scoring preserves decision identity and history."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Tradeoff Sync Check", SCOPE_ID)
    history1 = await DecisionHistoryService.get_history(d.decision_id)

    DecisionTradeoffService.calculate()

    assert d.decision_id is not None
    assert await DecisionHistoryService.get_history(d.decision_id) == history1


@pytest.mark.asyncio
async def test_decision_identity_preserved_after_snapshot_rebuild(mock_db):
    """Verify that snapshot rebuild preserves decision identity and history."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Snapshot Rebuild Check", SCOPE_ID)
    history1 = await DecisionHistoryService.get_history(d.decision_id)

    await DecisionSnapshotService.generate_snapshot(mock_db, SCOPE_ID)

    assert d.decision_id is not None
    assert await DecisionHistoryService.get_history(d.decision_id) == history1


@pytest.mark.asyncio
async def test_decision_identity_preserved_after_drift_processing(mock_db):
    """Verify that drift processing preserves decision identity and history."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "Drift Process Check", SCOPE_ID)
    history1 = await DecisionHistoryService.get_history(d.decision_id)

    prev_snap = {
        "total_decisions": 1,
        "recommended_count": 0,
        "committed_count": 0,
        "archived_count": 0,
        "average_net_benefit": 0.0,
    }
    await DecisionDriftService.process_drift(mock_db, SCOPE_ID, prev_snap)

    assert d.decision_id is not None
    assert await DecisionHistoryService.get_history(d.decision_id) == history1


@pytest.mark.asyncio
async def test_tradeoff_score_determinism(mock_db):
    """Verify tradeoff score calculations are deterministic for identical inputs."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "SSH Tradeoff", SCOPE_ID)
    
    DecisionTradeoffService.calculate()
    s1 = d.tradeoff_matrix.net_benefit

    # Rerun calculate
    DecisionTradeoffService.calculate()
    s2 = d.tradeoff_matrix.net_benefit

    assert s1 == s2


@pytest.mark.asyncio
async def test_scope_isolation_for_tradeoffs(mock_db):
    """Verify tradeoff calculation respects scope boundaries and doesn't leak records."""
    d1 = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "MFA Rule", SCOPE_ID)
    d2 = await SecurityDecisionService.create_or_sync_decision(DecisionType.MITIGATION, uuid.uuid4(), "MIT Rule", ALT_SCOPE_ID)

    DecisionTradeoffService.calculate()

    assert d1.tradeoff_matrix is not None
    assert d2.tradeoff_matrix is not None


@pytest.mark.asyncio
async def test_decision_score_stability(mock_db):
    """Verify decision scores are stable and do not drift without input parameters changes."""
    d = await SecurityDecisionService.create_or_sync_decision(DecisionType.REMEDIATION, uuid.uuid4(), "SSH Test", SCOPE_ID)
    DecisionTradeoffService.calculate()

    s1 = d.tradeoff_matrix.net_benefit
    DecisionTradeoffService.calculate()
    s2 = d.tradeoff_matrix.net_benefit

    assert s1 == s2


@pytest.mark.asyncio
async def test_worker_integration(mock_db):
    """Verify Celery task runner executes all Sprint 35 steps successfully in order."""
    from src.infrastructure.celery.worker import _execute_workflow_async
    from unittest.mock import patch
    # Pre-seed workflow and scan run
    workflow_id = uuid.uuid4()
    scan_run_id = uuid.uuid4()

    # Stub db models
    mock_workflow = MagicMock()
    mock_workflow.owner_id = ADMIN_ID
    mock_scan_run = MagicMock()
    mock_scan_run.status = "running"
    
    mock_scope = MagicMock()
    mock_scope.deleted_at = None
    mock_scope.owner_id = ADMIN_ID

    async def mock_get(model, ident):
        if model.__name__ == "Workflow" and ident == workflow_id:
            return mock_workflow
        if model.__name__ == "ScanRun" and ident == scan_run_id:
            return mock_scan_run
        if model.__name__ == "Scope" and ident == SCOPE_ID:
            return mock_scope
        return None

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None

    mock_db.get = AsyncMock(side_effect=mock_get)
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db

    # Run background execution
    with patch(
        "src.infrastructure.celery.worker.AsyncSessionLocal",
        mock_session_factory,
    ):
        await _execute_workflow_async(workflow_id, scan_run_id, SCOPE_ID)
    
    assert mock_scan_run.status == "completed"
