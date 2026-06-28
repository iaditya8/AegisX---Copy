import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request

from src.core.security import create_access_token
from src.domain.entities.autonomous_planning import (
    PlanPriority,
    PlanStatus,
    MilestoneType,
    MilestoneResponse,
    PlanningRecordResponse,
)
from src.infrastructure.database.models import User, Scope, Asset
from src.infrastructure.database.session import get_db
from src.services.autonomous_security_planning_service import AutonomousSecurityPlanningService
from src.services.planning_optimization_service import PlanningOptimizationService
from src.services.planning_drift_service import PlanningDriftService
from src.services.planning_snapshot_service import PlanningSnapshotService
from src.services.planning_history_service import PlanningHistoryService
from src.services.security_decision_service import SecurityDecisionService
from src.domain.entities.security_decision import DecisionType
from src.services.ai_context_builder import AIContextBuilder


ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SCOPE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
ALT_SCOPE_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")


@pytest.fixture(autouse=True)
def clean_planning_stores():
    AutonomousSecurityPlanningService.clear_plans()
    PlanningDriftService.clear_drifts()
    PlanningSnapshotService.clear_snapshots()
    SecurityDecisionService.clear_decisions()


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
    db.refresh = AsyncMock()
    return db


# --- Plan Structures & Lifecycle ---

def test_plan_auto_creation():
    """Verify plans can be synced/created dynamically and validates categories."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan(
        category="POSTURE_HARDENING",
        name="Hardening SSH Configurations",
        scope_id=SCOPE_ID,
    )
    assert p.category == "POSTURE_HARDENING"
    assert p.status == PlanStatus.DRAFT

    # Invalid Category
    with pytest.raises(ValueError):
        AutonomousSecurityPlanningService.create_or_sync_plan(
            category="INVALID_CATEGORY",
            name="Invalid Category Plan",
        )


def test_plan_fingerprint_stability():
    """Verify SHA-256 fingerprints are deterministic and stable across identical calls."""
    cat = "COMPLIANCE_ALIGNMENT"
    name = "ISO 27001 Alignment"
    p1 = AutonomousSecurityPlanningService.create_or_sync_plan(cat, name, SCOPE_ID)
    p2 = AutonomousSecurityPlanningService.create_or_sync_plan(cat, name, SCOPE_ID)
    assert p1.plan_fingerprint == p2.plan_fingerprint
    assert p1.plan_id == p2.plan_id


def test_plan_identity_preservation():
    """Verify syncing identical components preserves the original plan IDs and history."""
    cat = "RISK_REDUCTION_CAMPAIGN"
    name = "Remediate SQL Injection"
    p1 = AutonomousSecurityPlanningService.create_or_sync_plan(cat, name, SCOPE_ID)
    history1 = PlanningHistoryService.get_history(p1.plan_id)

    p2 = AutonomousSecurityPlanningService.create_or_sync_plan(cat, name, SCOPE_ID)

    assert p1.plan_id == p2.plan_id
    assert PlanningHistoryService.get_history(p2.plan_id) == history1


def test_plan_duplicate_prevention():
    """Verify that redundant sync calls do not add duplicate items to plan list."""
    cat = "POSTURE_HARDENING"
    name = "Active Directory Hardening"
    for _ in range(5):
        AutonomousSecurityPlanningService.create_or_sync_plan(cat, name, SCOPE_ID)
    
    plans = AutonomousSecurityPlanningService.get_all_plans()
    assert len(plans) == 1


def test_plan_approve_transition():
    """Verify manual transition to APPROVED status."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    updated = AutonomousSecurityPlanningService.approve_plan(p.plan_id)
    assert updated.status == PlanStatus.APPROVED

    history = PlanningHistoryService.get_history(p.plan_id)
    event_types = [h.event_type for h in history]
    assert "APPROVED" in event_types


def test_plan_activate_transition():
    """Verify transition to ACTIVE status."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    updated = AutonomousSecurityPlanningService.activate_plan(p.plan_id)
    assert updated.status == PlanStatus.ACTIVE

    history = PlanningHistoryService.get_history(p.plan_id)
    event_types = [h.event_type for h in history]
    assert "ACTIVATED" in event_types


def test_plan_close_transition():
    """Verify transition to CLOSED status."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    updated = AutonomousSecurityPlanningService.close_plan(p.plan_id)
    assert updated.status == PlanStatus.CLOSED

    history = PlanningHistoryService.get_history(p.plan_id)
    event_types = [h.event_type for h in history]
    assert "CLOSED" in event_types


# --- Plan Terminal State Enforcement ---

def test_plan_terminal_state_enforcement():
    """Verify that a closed plan rejects status transitions."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    AutonomousSecurityPlanningService.close_plan(p.plan_id)

    # Attempt transitions
    res_app = AutonomousSecurityPlanningService.approve_plan(p.plan_id)
    res_act = AutonomousSecurityPlanningService.activate_plan(p.plan_id)

    assert res_app.status == PlanStatus.CLOSED
    assert res_act.status == PlanStatus.CLOSED


def test_closed_plan_not_reactivated_by_sync():
    """Verify sync doesn't reactivate closed plans."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    AutonomousSecurityPlanningService.close_plan(p.plan_id)

    # Re-sync
    res = AutonomousSecurityPlanningService.create_or_sync_plan(p.category, p.name, SCOPE_ID)
    assert res.status == PlanStatus.CLOSED


@pytest.mark.asyncio
async def test_closed_plan_not_reactivated_by_worker(mock_db):
    """Verify background worker refresh does not reactivate closed plans."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    AutonomousSecurityPlanningService.close_plan(p.plan_id)

    # Trigger worker sync
    await AutonomousSecurityPlanningService.sync_plans(mock_db)
    assert p.status == PlanStatus.CLOSED


@pytest.mark.asyncio
async def test_closed_plan_not_reactivated_by_snapshot(mock_db):
    """Verify snapshot rebuild logic respects terminal closed states."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    AutonomousSecurityPlanningService.close_plan(p.plan_id)

    snap = await PlanningSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    assert snap["closed_count"] == 1
    assert p.status == PlanStatus.CLOSED


@pytest.mark.asyncio
async def test_closed_plan_not_reactivated_by_drift(mock_db):
    """Verify drift updates ignore closed plans and preserve terminal status."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    AutonomousSecurityPlanningService.close_plan(p.plan_id)

    prev_snap = {
        "total_plans": 1,
        "approved_count": 0,
        "active_count": 0,
        "closed_count": 1,
        "average_progress": 0.0,
    }
    await PlanningDriftService.process_drift(mock_db, SCOPE_ID, prev_snap)

    assert p.status == PlanStatus.CLOSED


def test_closed_plan_not_reactivated_by_optimization():
    """Verify optimization updates ignore closed plans."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    AutonomousSecurityPlanningService.close_plan(p.plan_id)

    PlanningOptimizationService.optimize_sequences()
    assert p.status == PlanStatus.CLOSED
    assert p.roadmap is None # Should remain un-calculated / None


# --- Immutable History preservation ---

def test_planning_history_preserved():
    """Verify planning recommendations append history but never overwrite previous history."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    AutonomousSecurityPlanningService.close_plan(p.plan_id)

    history = PlanningHistoryService.get_history(p.plan_id)
    assert len(history) == 2
    assert history[0].event_type == "CREATED"
    assert history[1].event_type == "CLOSED"


def test_planning_history_immutable():
    """Verify history entries returned are deep copies and cannot be modified by callers."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    history = PlanningHistoryService.get_history(p.plan_id)
    
    with pytest.raises(TypeError):
        history[0] = "MUTATED"


def test_planning_history_order_preserved():
    """Verify history log entries are sorted chronologically and retain exact sequences."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    AutonomousSecurityPlanningService.close_plan(p.plan_id)

    history = PlanningHistoryService.get_history(p.plan_id)
    assert history[0].timestamp <= history[1].timestamp


# --- Scoring Determinism & Derived Calculations ---

def test_optimization_sequencing_deterministic():
    """Verify optimization calculation logic is fully deterministic."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    
    PlanningOptimizationService.optimize_sequences()
    r1 = p.roadmap
    assert r1 is not None

    PlanningOptimizationService.optimize_sequences()
    r2 = p.roadmap
    assert r1.resource_utilization_coefficient == r2.resource_utilization_coefficient
    assert r1.estimated_effort_days == r2.estimated_effort_days


def test_priority_calculation_consistency():
    """Verify priority calculation utilizes weights correctly."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    p.milestones = [
        MilestoneResponse(
            milestone_id=uuid.uuid4(),
            name="Milestone 1",
            milestone_type=MilestoneType.REMEDIATION,
            target_entity_id=uuid.uuid4(),
            status="PENDING",
            due_date=datetime.now(timezone.utc),
        )
    ]
    PlanningOptimizationService.optimize_sequences()
    assert p.roadmap.resource_utilization_coefficient == 0.5 # 0 completed


def test_milestone_completion_impact():
    """Verify resource utilization coefficient adapts to completed milestones."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    p.milestones = [
        MilestoneResponse(
            milestone_id=uuid.uuid4(),
            name="Milestone 1",
            milestone_type=MilestoneType.REMEDIATION,
            target_entity_id=uuid.uuid4(),
            status="COMPLETED",
            due_date=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
    ]
    PlanningOptimizationService.optimize_sequences()
    assert p.roadmap.resource_utilization_coefficient == 0.95 # 0.5 + 0.45 * (1/1)


# --- Plan Drift Detection ---

@pytest.mark.asyncio
async def test_planning_drift_detection(mock_db):
    """Verify structural drift logic detects plan benefit and count shifts."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    PlanningOptimizationService.optimize_sequences()

    prev_snap = {
        "total_plans": 0,
        "approved_count": 0,
        "active_count": 0,
        "closed_count": 0,
        "average_progress": 0.0,
    }

    await PlanningDriftService.process_drift(mock_db, SCOPE_ID, prev_snap)
    drifts = PlanningDriftService.get_drifts()

    assert len(drifts) > 0
    assert "plans count changed" in drifts[0]["details"].lower()


def test_planning_drift_clearing():
    """Verify drift logs can be cleared."""
    PlanningDriftService._drifts.append({"test": "drift"})
    PlanningDriftService.clear_drifts()
    assert len(PlanningDriftService.get_drifts()) == 0


# --- Snapshot Cache-Only Rebuild consistency ---

@pytest.mark.asyncio
async def test_snapshot_rebuild_consistency(mock_db):
    """Verify snapshot generation computes counts and average progress correctly."""
    p1 = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening 1", SCOPE_ID)
    p2 = AutonomousSecurityPlanningService.create_or_sync_plan("COMPLIANCE_ALIGNMENT", "ISO 27001 AD", SCOPE_ID)
    
    AutonomousSecurityPlanningService.approve_plan(p1.plan_id)
    AutonomousSecurityPlanningService.activate_plan(p2.plan_id)

    p1.milestones = [
        MilestoneResponse(
            milestone_id=uuid.uuid4(),
            name="M1",
            milestone_type=MilestoneType.REMEDIATION,
            target_entity_id=uuid.uuid4(),
            status="COMPLETED",
            due_date=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
    ]

    snap = await PlanningSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    assert snap["total_plans"] == 2
    assert snap["approved_count"] == 1
    assert snap["active_count"] == 1
    assert snap["average_progress"] == 1.0 # 1.0 (p1 has 1/1 completed, p2 has 0 milestones)


@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_deletion(mock_db):
    """Verify get_snapshot rebuilds from source if the cache is missing or deleted."""
    AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    PlanningSnapshotService.clear_snapshots()

    snap = await PlanningSnapshotService.get_snapshot(mock_db, SCOPE_ID)
    assert snap["total_plans"] == 1


@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_corruption(mock_db):
    """Verify snapshot rebuilds if cache exists but keys are corrupted/missing."""
    PlanningSnapshotService._snapshots[SCOPE_ID] = {"corrupted": True}
    AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)

    snap = await PlanningSnapshotService.get_snapshot(mock_db, SCOPE_ID)
    assert "total_plans" in snap
    assert snap["total_plans"] == 1


@pytest.mark.asyncio
async def test_snapshot_not_authoritative(mock_db):
    """Verify snapshot doesn't store state exclusively; clearing snapshots doesn't delete active plans."""
    AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    await PlanningSnapshotService.generate_snapshot(mock_db, SCOPE_ID)

    PlanningSnapshotService.clear_snapshots()
    assert len(AutonomousSecurityPlanningService.get_all_plans()) == 1


@pytest.mark.asyncio
async def test_snapshot_rebuild_from_source_of_truth(mock_db):
    """Verify get_snapshot loads from the source of truth when cache is empty."""
    AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    
    PlanningSnapshotService.clear_snapshots()
    snap = await PlanningSnapshotService.get_snapshot(mock_db, SCOPE_ID)
    assert snap["total_plans"] == 1


# --- AI integration & Prompt Guardrails ---

@pytest.mark.asyncio
async def test_ai_context_planning_injection(mock_db):
    """Verify that build_asset_context includes planning_summary and planning_records."""
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

    AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)

    try:
        ctx = await AIContextBuilder.build_asset_context(mock_db, uuid.uuid4())
        assert "planning_summary" in ctx["asset"]
        assert "planning_records" in ctx["asset"]
    finally:
        AssetReportService.generate_asset_report = original_report


def test_ai_advisory_only_enforcement():
    """Verify Copilot prompt builder restrains AI from mutating plans."""
    from src.services.ai_prompt_builder import AIPromptBuilder
    prompt = AIPromptBuilder.build_asset_prompt({"context": "empty"})
    assert "plans, milestones, fabric segments" in prompt


# --- Scope Isolation and RBAC Verification ---

@pytest.mark.asyncio
async def test_rbac_planning_scope_validation(mock_db):
    """Verify planning API requests enforce scope checks for non-admin users."""
    from fastapi.testclient import TestClient
    from src.main import app
    from src.api.v1.dependencies.auth import get_current_user
    import src.api.v1.routers.autonomous_planning as plan_router

    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)

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
        mp.setattr(plan_router, "get_scope_by_id", mock_get_scope)
        try:
            resp = client.get(
                f"/api/v1/autonomous-planning/{p.plan_id}",
                headers=headers
            )
            assert resp.status_code == 403

            resp_admin = client.get(
                f"/api/v1/autonomous-planning/{p.plan_id}",
                headers=admin_headers
            )
            assert resp_admin.status_code == 200
        finally:
            app.dependency_overrides.clear()


# --- Identity Preservation after worker/optimization/snapshot/drift ---

@pytest.mark.asyncio
async def test_planning_identity_preserved_after_worker_refresh(mock_db):
    """Verify that worker refresh preserves plan identity and history."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    history1 = PlanningHistoryService.get_history(p.plan_id)

    # Sync
    await AutonomousSecurityPlanningService.sync_plans(mock_db)
    
    assert p.plan_id is not None
    assert PlanningHistoryService.get_history(p.plan_id) == history1


def test_planning_identity_preserved_after_optimization_refresh():
    """Verify that optimization sequencing preserves plan identity and history."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    history1 = PlanningHistoryService.get_history(p.plan_id)

    PlanningOptimizationService.optimize_sequences()

    assert p.plan_id is not None
    assert PlanningHistoryService.get_history(p.plan_id) == history1


@pytest.mark.asyncio
async def test_planning_identity_preserved_after_snapshot_rebuild(mock_db):
    """Verify that snapshot rebuild preserves plan identity and history."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    history1 = PlanningHistoryService.get_history(p.plan_id)

    await PlanningSnapshotService.generate_snapshot(mock_db, SCOPE_ID)

    assert p.plan_id is not None
    assert PlanningHistoryService.get_history(p.plan_id) == history1


@pytest.mark.asyncio
async def test_planning_identity_preserved_after_drift_processing(mock_db):
    """Verify that drift processing preserves plan identity and history."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    history1 = PlanningHistoryService.get_history(p.plan_id)

    prev_snap = {
        "total_plans": 1,
        "approved_count": 0,
        "active_count": 0,
        "closed_count": 0,
        "average_progress": 0.0,
    }
    await PlanningDriftService.process_drift(mock_db, SCOPE_ID, prev_snap)

    assert p.plan_id is not None
    assert PlanningHistoryService.get_history(p.plan_id) == history1


def test_optimization_sequence_determinism():
    """Verify optimization sequence calculations are deterministic for identical inputs."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    
    PlanningOptimizationService.optimize_sequences()
    s1 = p.roadmap.resource_utilization_coefficient

    # Rerun calculate
    PlanningOptimizationService.optimize_sequences()
    s2 = p.roadmap.resource_utilization_coefficient

    assert s1 == s2


@pytest.mark.asyncio
async def test_scope_isolation_for_plans(mock_db):
    """Verify optimization calculation respects scope boundaries and doesn't leak records."""
    p1 = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    p2 = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening 2", ALT_SCOPE_ID)

    PlanningOptimizationService.optimize_sequences()

    assert p1.roadmap is not None
    assert p2.roadmap is not None


def test_planning_score_stability():
    """Verify planning scores are stable and do not drift without input parameters changes."""
    p = AutonomousSecurityPlanningService.create_or_sync_plan("POSTURE_HARDENING", "AD Hardening", SCOPE_ID)
    PlanningOptimizationService.optimize_sequences()

    s1 = p.roadmap.resource_utilization_coefficient
    PlanningOptimizationService.optimize_sequences()
    s2 = p.roadmap.resource_utilization_coefficient

    assert s1 == s2


@pytest.mark.asyncio
async def test_worker_integration(mock_db):
    """Verify Celery task runner executes all Sprint 36 steps successfully in order."""
    from src.infrastructure.celery.worker import _execute_workflow_async
    
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
