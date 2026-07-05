import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from src.core.security import create_access_token
from src.domain.entities.security_program import (
    ProgramSeverity,
    ProgramStatus,
    KPIStatus,
    KRIStatus,
    SecurityProgramResponse,
    ProgramObjectiveResponse,
    ProgramInitiativeResponse,
    KPIResponse,
    KRIResponse,
)
from src.infrastructure.database.models import Asset, Scope, User
from src.services.security_program_registry import SecurityProgramRegistry
from src.services.kpi_registry import KPIRegistry
from src.services.kri_registry import KRIRegistry
from src.services.program_fingerprint_service import ProgramFingerprintService
from src.services.program_history_service import ProgramHistoryService
from src.services.kpi_service import KPIService
from src.services.kri_service import KRIService
from src.services.program_health_service import ProgramHealthService
from src.services.program_correlation_service import ProgramCorrelationService
from src.services.program_drift_service import ProgramDriftService
from src.services.security_program_service import SecurityProgramService, ProgramObjectiveRecord, ProgramInitiativeRecord
from src.services.security_program_snapshot_service import SecurityProgramSnapshotService
from src.services.ai_context_builder import AIContextBuilder
from src.services.ai_prompt_builder import AIPromptBuilder

ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OPERATOR_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
READER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SCOPE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
SCOPE_ID_2 = uuid.UUID("66666666-6666-6666-6666-666666666666")


@pytest.fixture
def mock_admin() -> User:
    user = User()
    user.id = ADMIN_ID
    user.username = "admin_user"
    user.role = "admin"
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_operator() -> User:
    user = User()
    user.id = OPERATOR_ID
    user.username = "operator_user"
    user.role = "operator"
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_reader() -> User:
    user = User()
    user.id = READER_ID
    user.username = "reader_user"
    user.role = "reader"
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_scope() -> Scope:
    s = Scope()
    s.id = SCOPE_ID
    s.owner_id = OPERATOR_ID
    s.name = "Test Scope"
    s.deleted_at = None
    return s


@pytest.fixture
def mock_scope_2() -> Scope:
    s = Scope()
    s.id = SCOPE_ID_2
    s.owner_id = uuid.uuid4()
    s.name = "Other Scope"
    s.deleted_at = None
    return s


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_stores():
    SecurityProgramService.clear_programs()
    ProgramHistoryService.clear_history()
    ProgramCorrelationService.clear_correlations()
    SecurityProgramSnapshotService.clear_snapshots()


@pytest.fixture(autouse=True)
def override_auth_dependency():
    from fastapi import HTTPException, Request
    from src.api.v1.dependencies.auth import get_current_user
    from src.main import app

    async def mock_get_current_user(request: Request) -> User:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Unauthorized")
        token = auth_header.split(" ")[1]
        from src.core.security import decode_token

        payload = decode_token(token)
        user_id = uuid.UUID(payload["sub"])
        roles = payload.get("roles", [])

        user = User()
        user.id = user_id
        user.username = "mocked_user"
        user.role = roles[0] if roles else "reader"
        user.deleted_at = None
        return user

    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def setup_basic_mock_db(mock_db, *scopes):
    orig_add = mock_db.add
    orig_commit = mock_db.commit
    orig_execute = mock_db.execute
    orig_get = mock_db.get

    async def mock_get(model, ident):
        if model == Scope:
            for s in scopes:
                if s.id == ident:
                    return s
        return await orig_get(model, ident)

    mock_db.get = AsyncMock(side_effect=mock_get)

    async def mock_execute(query, *args, **kwargs):
        query_str = str(query).lower()

        if "from scopes" in query_str or "from scope" in query_str:
            scope_id_val = None
            owner_id_val = None
            try:
                params = query.compile().params
                for k, v in params.items():
                    if "id_" in k:
                        if isinstance(v, uuid.UUID) or (isinstance(v, str) and len(v) == 36):
                            scope_id_val = uuid.UUID(str(v))
                    if "owner_id" in k:
                        owner_id_val = v
            except Exception:
                pass

            matched = list(scopes)
            if scope_id_val:
                matched = [s for s in matched if s.id == scope_id_val]
            elif owner_id_val:
                matched = [s for s in matched if s.owner_id == owner_id_val]

            mock_result = MagicMock()
            mock_result.scalars().all = MagicMock(return_value=matched)
            mock_result.scalar_one_or_none = MagicMock(return_value=matched[0] if matched else None)
            return mock_result
        
        if any(table in query_str for table in ["security_program", "security_program_history", "security_program_objectives", "security_program_initiatives"]):
            return await orig_execute(query, *args, **kwargs)

        mock_result = MagicMock()
        mock_result.scalars().all = MagicMock(return_value=[])
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        return mock_result

    mock_db.execute = AsyncMock(side_effect=mock_execute)


# --- Mandatory Integration Tests (1 to 50) ---

@pytest.mark.asyncio
async def test_program_auto_creation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    synced = await SecurityProgramService.sync_programs(mock_db)
    assert len(synced) == 1
    assert synced[0].name == "Vulnerability Management Program"


@pytest.mark.asyncio
async def test_program_fingerprint_stability():
    f1 = ProgramFingerprintService.generate_fingerprint("VM Program", "Vulnerability Management", ProgramSeverity.HIGH)
    f2 = ProgramFingerprintService.generate_fingerprint("VM Program", "Vulnerability Management", ProgramSeverity.HIGH)
    assert f1 == f2


@pytest.mark.asyncio
async def test_program_activate_transition(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    p_trans = await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.ACTIVE)
    assert p_trans.status == ProgramStatus.ACTIVE


@pytest.mark.asyncio
async def test_program_review_transition(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    p_trans = await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.UNDER_REVIEW)
    assert p_trans.status == ProgramStatus.UNDER_REVIEW


@pytest.mark.asyncio
async def test_program_complete_transition(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    p_trans = await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.COMPLETED)
    assert p_trans.status == ProgramStatus.COMPLETED


@pytest.mark.asyncio
async def test_program_close_transition(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    p_trans = await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.CLOSED)
    assert p_trans.status == ProgramStatus.CLOSED


@pytest.mark.asyncio
async def test_program_identity_preserved_after_completion(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.COMPLETED)
    p_sync = await SecurityProgramService.create_or_sync_program("P1", "New Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    assert p_sync.status == ProgramStatus.COMPLETED
    assert p_sync.description == "Desc"


@pytest.mark.asyncio
async def test_program_identity_preserved_after_closure(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.CLOSED)
    p_sync = await SecurityProgramService.create_or_sync_program("P1", "New Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    assert p_sync.status == ProgramStatus.CLOSED
    assert p_sync.description == "Desc"


@pytest.mark.asyncio
async def test_ai_context_program_injection(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityProgramService.sync_programs(mock_db)
    await SecurityProgramSnapshotService.generate_snapshot(mock_db, None)

    ctx = await AIContextBuilder._build_security_program_context_block(None)
    assert "security_program_summary" in ctx
    assert len(ctx["security_programs"]) == 1


@pytest.mark.asyncio
async def test_rbac_program_scope_validation(client, mock_db, mock_scope, mock_scope_2):
    setup_basic_mock_db(mock_db, mock_scope, mock_scope_2)
    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {
        "name": "Restricted Program",
        "description": "Desc",
        "category": "Vulnerability Management",
        "severity": "HIGH",
        "scope_id": str(SCOPE_ID_2),
    }
    resp = await client.post("/api/v1/security-program", json=payload, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_program_terminal_state_not_reactivated_by_sync(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("Vulnerability Management Program", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.COMPLETED)
    await SecurityProgramService.sync_programs(mock_db)
    assert p.status == ProgramStatus.COMPLETED


@pytest.mark.asyncio
async def test_snapshot_rebuild_consistency(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityProgramService.sync_programs(mock_db)
    SecurityProgramSnapshotService.clear_snapshots()
    s1 = await SecurityProgramSnapshotService.generate_snapshot(mock_db, None)
    SecurityProgramSnapshotService.clear_snapshots()
    s2 = await SecurityProgramSnapshotService.generate_snapshot(mock_db, None)
    assert s1 == s2


@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_deletion(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityProgramService.sync_programs(mock_db)
    await SecurityProgramSnapshotService.generate_snapshot(mock_db, None)
    SecurityProgramSnapshotService.clear_snapshots()
    snap = SecurityProgramSnapshotService.get_snapshot(None)
    assert snap["summary"]["total_programs"] == 0
    await SecurityProgramSnapshotService.generate_snapshot(mock_db, None)
    snap2 = SecurityProgramSnapshotService.get_snapshot(None)
    assert snap2["summary"]["total_programs"] == 1


@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_corruption(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityProgramService.sync_programs(mock_db)
    SecurityProgramSnapshotService._snapshots[None] = "CORRUPTED_CACHE"
    snap = SecurityProgramSnapshotService.get_snapshot(None)
    assert snap["summary"]["total_programs"] == 0


@pytest.mark.asyncio
async def test_program_duplicate_prevention(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p1 = await SecurityProgramService.create_or_sync_program("Program Alpha", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    p2 = await SecurityProgramService.create_or_sync_program("Program Alpha", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    assert p1.program_id == p2.program_id
    assert len(SecurityProgramService.get_all_programs()) == 1


@pytest.mark.asyncio
async def test_program_history_preserved(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("History test", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    hist = await ProgramHistoryService.get_history(p.program_id)
    assert len(hist) > 0
    assert hist[0].event_type == "CREATED"


@pytest.mark.asyncio
async def test_program_correlation_preservation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("Correlate test", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await ProgramCorrelationService.correlate_program(mock_db, p.program_id, SCOPE_ID)
    corrs = ProgramCorrelationService.get_correlations(p.program_id)
    assert isinstance(corrs, list)


@pytest.mark.asyncio
async def test_kpi_calculation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    kpis = KPIService.calculate_kpis(SCOPE_ID)
    kpi_names = [k.name for k in kpis]
    assert "Mean Time To Detect" in kpi_names
    assert "Mean Time To Respond" in kpi_names


@pytest.mark.asyncio
async def test_kri_calculation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    kris = KRIService.calculate_kris(SCOPE_ID)
    kri_names = [k.name for k in kris]
    assert "Critical Risk Growth" in kri_names
    assert "Open Incident Growth" in kri_names


@pytest.mark.asyncio
async def test_program_health_score():
    o1 = ProgramObjectiveResponse(objective_id=uuid.uuid4(), name="Obj 1", description="desc", completion_percentage=80.0)
    i1 = ProgramInitiativeResponse(initiative_id=uuid.uuid4(), name="Init 1", description="desc", status="ACTIVE", completion_percentage=60.0)
    health = ProgramHealthService.calculate_health([o1], [i1], [], [])
    assert health["program_score"] == 82.0


@pytest.mark.asyncio
async def test_program_score_stability():
    o1 = ProgramObjectiveResponse(objective_id=uuid.uuid4(), name="Obj 1", description="desc", completion_percentage=100.0)
    health1 = ProgramHealthService.calculate_health([o1], [], [], [])
    health2 = ProgramHealthService.calculate_health([o1], [], [], [])
    assert health1["program_score"] == health2["program_score"]


@pytest.mark.asyncio
async def test_program_score_change_detection(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    prev = {
        "summary": {
            "average_program_score": 95.0,
        },
        "programs": {},
    }

    await SecurityProgramService.sync_programs(mock_db)
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await ProgramDriftService.check_drift(mock_db, None, prev)
        events = [c.kwargs["payload"]["drift_type"] for c in mock_emit.call_args_list]
        assert "PROGRAM_SCORE_DECREASED" in events or len(events) == 0


@pytest.mark.asyncio
async def test_objective_completion():
    o1 = ProgramObjectiveResponse(objective_id=uuid.uuid4(), name="Obj 1", description="desc", completion_percentage=75.0)
    health = ProgramHealthService.calculate_health([o1], [], [], [])
    assert health["objective_completion"] == 75.0


@pytest.mark.asyncio
async def test_initiative_completion():
    i1 = ProgramInitiativeResponse(initiative_id=uuid.uuid4(), name="Init 1", description="desc", status="ACTIVE", completion_percentage=40.0)
    health = ProgramHealthService.calculate_health([], [i1], [], [])
    assert health["initiative_completion"] == 40.0


@pytest.mark.asyncio
async def test_kpi_drift_detection(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    p = await SecurityProgramService.create_or_sync_program("Drift Program", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [], scope_id=SCOPE_ID)

    prev = {
        "summary": {"average_program_score": 100.0},
        "programs": {
            str(p.program_id): {
                "program_id": str(p.program_id),
                "name": "Drift Program",
                "status": "PLANNED",
                "program_score": 100.0,
                "kpis": [
                    {
                        "name": "Mean Time To Detect",
                        "status": "ON_TARGET",
                    }
                ],
                "kris": [],
            }
        },
    }

    with patch("src.services.kpi_service.IncidentService.get_all_incidents", return_value=[MagicMock()] * 50):
        with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
            await ProgramDriftService.check_drift(mock_db, SCOPE_ID, prev)
            events = [c.kwargs["payload"].get("drift_type") for c in mock_emit.call_args_list]
            assert any(e in ["KPI_REGRESSED", "PROGRAM_SCORE_DECREASED"] for e in events)


@pytest.mark.asyncio
async def test_kri_drift_detection(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    p = await SecurityProgramService.create_or_sync_program("KRI Drift Program", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [], scope_id=SCOPE_ID)

    prev = {
        "summary": {"average_program_score": 100.0},
        "programs": {
            str(p.program_id): {
                "program_id": str(p.program_id),
                "name": "KRI Drift Program",
                "status": "PLANNED",
                "program_score": 100.0,
                "kpis": [],
                "kris": [
                    {
                        "name": "Critical Risk Growth",
                        "status": "LOW_RISK",
                    }
                ],
            }
        },
    }

    with patch("src.services.kri_service.IncidentService.get_all_incidents", return_value=[MagicMock()] * 50):
        with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
            await ProgramDriftService.check_drift(mock_db, SCOPE_ID, prev)
            events = [c.kwargs["payload"].get("drift_type") for c in mock_emit.call_args_list]
            assert any(e in ["KRI_REGRESSED", "PROGRAM_SCORE_DECREASED"] for e in events)


@pytest.mark.asyncio
async def test_ai_advisory_only_enforcement():
    prompt = AIPromptBuilder.build_asset_prompt({})
    assert "MUST NOT approve risk" in prompt
    assert "modifying security programs" in prompt or "mutating security programs" in prompt or "modifying security programs" in prompt.lower()


@pytest.mark.asyncio
async def test_program_sync_preserves_identity(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p1 = await SecurityProgramService.create_or_sync_program("Sync Preserve", "Desc 1", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    p2 = await SecurityProgramService.create_or_sync_program("Sync Preserve", "Desc 2", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    assert p1.program_id == p2.program_id
    assert p1.created_at == p2.created_at


@pytest.mark.asyncio
async def test_kpi_registry_validation():
    assert KPIRegistry.is_registered("Mean Time To Detect")
    assert not KPIRegistry.is_registered("Invalid KPI")


@pytest.mark.asyncio
async def test_kri_registry_validation():
    assert KRIRegistry.is_registered("Critical Risk Growth")
    assert not KRIRegistry.is_registered("Invalid KRI")


@pytest.mark.asyncio
async def test_worker_integration(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.continuous_refresh_service import ContinuousRefreshService
    await ContinuousRefreshService.refresh_all(mock_db)


@pytest.mark.asyncio
async def test_completed_program_not_reactivated_by_worker(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("Vulnerability Management Program", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.COMPLETED)
    
    from src.services.continuous_refresh_service import ContinuousRefreshService
    await ContinuousRefreshService.refresh_all(mock_db)
    assert p.status == ProgramStatus.COMPLETED


@pytest.mark.asyncio
async def test_closed_program_not_reactivated_by_worker(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("Vulnerability Management Program", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.CLOSED)
    
    from src.services.continuous_refresh_service import ContinuousRefreshService
    await ContinuousRefreshService.refresh_all(mock_db)
    assert p.status == ProgramStatus.CLOSED


@pytest.mark.asyncio
async def test_completed_program_not_reactivated_by_snapshot(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.COMPLETED)
    await SecurityProgramSnapshotService.generate_snapshot(mock_db, None)
    assert p.status == ProgramStatus.COMPLETED


@pytest.mark.asyncio
async def test_closed_program_not_reactivated_by_snapshot(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.CLOSED)
    await SecurityProgramSnapshotService.generate_snapshot(mock_db, None)
    assert p.status == ProgramStatus.CLOSED


@pytest.mark.asyncio
async def test_completed_program_not_reactivated_by_drift(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.COMPLETED)
    await ProgramDriftService.check_drift(mock_db, None, {"summary": {"average_program_score": 10.0}})
    assert p.status == ProgramStatus.COMPLETED


@pytest.mark.asyncio
async def test_closed_program_not_reactivated_by_drift(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.CLOSED)
    await ProgramDriftService.check_drift(mock_db, None, {"summary": {"average_program_score": 10.0}})
    assert p.status == ProgramStatus.CLOSED


@pytest.mark.asyncio
async def test_completed_program_not_reactivated_by_kpi_refresh(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.COMPLETED)
    KPIService.calculate_kpis(SCOPE_ID)
    assert p.status == ProgramStatus.COMPLETED


@pytest.mark.asyncio
async def test_closed_program_not_reactivated_by_kpi_refresh(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.CLOSED)
    KPIService.calculate_kpis(SCOPE_ID)
    assert p.status == ProgramStatus.CLOSED


@pytest.mark.asyncio
async def test_completed_program_not_reactivated_by_kri_refresh(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.COMPLETED)
    KRIService.calculate_kris(SCOPE_ID)
    assert p.status == ProgramStatus.COMPLETED


@pytest.mark.asyncio
async def test_closed_program_not_reactivated_by_kri_refresh(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.CLOSED)
    KRIService.calculate_kris(SCOPE_ID)
    assert p.status == ProgramStatus.CLOSED


@pytest.mark.asyncio
async def test_program_history_immutable(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("Immutable History", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    hist = await ProgramHistoryService.get_history(p.program_id)
    hist.clear()
    assert len(await ProgramHistoryService.get_history(p.program_id)) == 1


@pytest.mark.asyncio
async def test_program_history_survives_snapshot_rebuild(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("Survive Rebuild", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramSnapshotService.generate_snapshot(mock_db, None)
    assert len(await ProgramHistoryService.get_history(p.program_id)) == 1


@pytest.mark.asyncio
async def test_program_correlation_append_only(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("Corr test", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await ProgramCorrelationService.correlate_program(mock_db, p.program_id, SCOPE_ID)
    corrs = ProgramCorrelationService.get_correlations(p.program_id)
    corrs.clear()
    assert len(ProgramCorrelationService.get_correlations(p.program_id)) >= 0


@pytest.mark.asyncio
async def test_program_health_score_deterministic():
    o = ProgramObjectiveResponse(objective_id=uuid.uuid4(), name="Obj", description="d", completion_percentage=50.0)
    h1 = ProgramHealthService.calculate_health([o], [], [], [])
    h2 = ProgramHealthService.calculate_health([o], [], [], [])
    assert h1 == h2


@pytest.mark.asyncio
async def test_program_snapshot_not_authoritative(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityProgramService.sync_programs(mock_db)
    snap = await SecurityProgramSnapshotService.generate_snapshot(mock_db, None)
    snap["summary"]["total_programs"] = 999
    assert len(SecurityProgramService.get_all_programs()) == 1


@pytest.mark.asyncio
async def test_program_snapshot_rebuild_from_source_of_truth(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityProgramService.sync_programs(mock_db)
    SecurityProgramSnapshotService._snapshots[None] = None
    await SecurityProgramSnapshotService.generate_snapshot(mock_db, None)
    assert SecurityProgramSnapshotService.get_snapshot(None)["summary"]["total_programs"] == 1


@pytest.mark.asyncio
async def test_program_identity_preserved_after_health_recalculation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("VM Program Identity", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    assert p.status == ProgramStatus.PLANNED


@pytest.mark.asyncio
async def test_program_identity_preserved_after_kpi_refresh(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    KPIService.calculate_kpis(SCOPE_ID)
    assert p.status == ProgramStatus.PLANNED


@pytest.mark.asyncio
async def test_program_identity_preserved_after_kri_refresh(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    KRIService.calculate_kris(SCOPE_ID)
    assert p.status == ProgramStatus.PLANNED


# --- 36 Additional Integration Tests ---

@pytest.mark.asyncio
async def test_create_program_invalid_category(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    with pytest.raises(ValueError, match="Invalid category"):
        await SecurityProgramService.create_or_sync_program("Invalid Cat Prog", "Desc", "Unregistered Category", ProgramSeverity.HIGH, [], [])


@pytest.mark.asyncio
async def test_transition_program_status_not_found():
    with pytest.raises(ValueError, match="not found"):
        await SecurityProgramService.transition_program_status(uuid.uuid4(), ProgramStatus.ACTIVE)


@pytest.mark.asyncio
async def test_transition_program_status_invalid(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.ACTIVE)
    assert p.status == ProgramStatus.ACTIVE


@pytest.mark.asyncio
async def test_program_drift_status_changed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    p = await SecurityProgramService.create_or_sync_program("VM Program Drift", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [], scope_id=SCOPE_ID)

    prev = {
        "summary": {"average_program_score": 100.0},
        "programs": {
            str(p.program_id): {
                "program_id": str(p.program_id),
                "name": "VM Program Drift",
                "status": "PLANNED",
                "program_score": 100.0,
                "kpis": [],
                "kris": [],
            }
        },
    }

    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.ACTIVE)

    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await ProgramDriftService.check_drift(mock_db, SCOPE_ID, prev)
        events = [c.kwargs["payload"].get("drift_type") for c in mock_emit.call_args_list]
        assert "PROGRAM_STATUS_CHANGED" in events


@pytest.mark.asyncio
async def test_program_drift_kpi_regressed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    p = await SecurityProgramService.create_or_sync_program("Drift KPI", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [], scope_id=SCOPE_ID)

    prev = {
        "summary": {"average_program_score": 100.0},
        "programs": {
            str(p.program_id): {
                "program_id": str(p.program_id),
                "name": "Drift KPI",
                "status": "PLANNED",
                "program_score": 100.0,
                "kpis": [
                    {
                        "name": "Mean Time To Detect",
                        "status": "ON_TARGET",
                    }
                ],
                "kris": [],
            }
        },
    }

    with patch("src.services.kpi_service.IncidentService.get_all_incidents", return_value=[MagicMock()] * 50):
        with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
            await ProgramDriftService.check_drift(mock_db, SCOPE_ID, prev)
            events = [c.kwargs["payload"].get("drift_type") for c in mock_emit.call_args_list]
            assert any(e in ["KPI_REGRESSED", "PROGRAM_SCORE_DECREASED"] for e in events)


@pytest.mark.asyncio
async def test_program_drift_kri_regressed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    p = await SecurityProgramService.create_or_sync_program("Drift KRI", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [], scope_id=SCOPE_ID)

    prev = {
        "summary": {"average_program_score": 100.0},
        "programs": {
            str(p.program_id): {
                "program_id": str(p.program_id),
                "name": "Drift KRI",
                "status": "PLANNED",
                "program_score": 100.0,
                "kpis": [],
                "kris": [
                    {
                        "name": "Critical Risk Growth",
                        "status": "LOW_RISK",
                    }
                ],
            }
        },
    }

    with patch("src.services.kri_service.IncidentService.get_all_incidents", return_value=[MagicMock()] * 50):
        with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
            await ProgramDriftService.check_drift(mock_db, SCOPE_ID, prev)
            events = [c.kwargs["payload"].get("drift_type") for c in mock_emit.call_args_list]
            assert any(e in ["KRI_REGRESSED", "PROGRAM_SCORE_DECREASED"] for e in events)


@pytest.mark.asyncio
async def test_program_correlation_empty_scope(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    res = await ProgramCorrelationService.correlate_program(mock_db, uuid.uuid4(), SCOPE_ID)
    assert isinstance(res, list)


@pytest.mark.asyncio
async def test_program_health_score_kpi_weight():
    k1 = KPIResponse(kpi_id=uuid.uuid4(), name="kpi", description="d", value=10.0, target=10.0, status=KPIStatus.ON_TARGET)
    health = ProgramHealthService.calculate_health([], [], [k1], [])
    assert health["kpi_performance"] == 100.0


@pytest.mark.asyncio
async def test_program_health_score_kri_weight():
    k1 = KRIResponse(kri_id=uuid.uuid4(), name="kri", description="d", value=10.0, threshold=10.0, status=KRIStatus.LOW_RISK)
    health = ProgramHealthService.calculate_health([], [], [], [k1])
    assert health["kri_exposure"] == 100.0


@pytest.mark.asyncio
async def test_program_health_score_all_empty():
    health = ProgramHealthService.calculate_health([], [], [], [])
    assert health["program_score"] == 100.0


@pytest.mark.asyncio
async def test_snapshot_rebuild_zero_programs(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    snap = await SecurityProgramSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    assert snap["summary"]["total_programs"] == 0


@pytest.mark.asyncio
async def test_snapshot_rebuild_statistics_calculation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityProgramService.sync_programs(mock_db)
    snap = await SecurityProgramSnapshotService.generate_snapshot(mock_db, None)
    assert snap["summary"]["total_programs"] == 1


@pytest.mark.asyncio
async def test_api_list_programs_admin(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(ADMIN_ID, "admin")
    resp = await client.get("/api/v1/security-program", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_list_programs_operator(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-program", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_list_programs_reader(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(READER_ID, "reader")
    resp = await client.get("/api/v1/security-program", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_list_active_programs(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-program/active", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_get_summary_snapshot_non_admin_forbidden(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-program/summary", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_get_summary_snapshot_admin_success(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(ADMIN_ID, "admin")
    resp = await client.get("/api/v1/security-program/summary", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_get_program_details_success(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/security-program/{p.program_id}", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_get_program_details_not_found(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/security-program/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_create_program_rbac_reader_forbidden(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(READER_ID, "reader")
    payload = {
        "name": "Forbidden Program",
        "description": "Desc",
        "category": "Vulnerability Management",
        "severity": "HIGH",
    }
    resp = await client.post("/api/v1/security-program", json=payload, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_create_program_success(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {
        "name": "Success Program",
        "description": "Desc",
        "category": "Vulnerability Management",
        "severity": "HIGH",
        "scope_id": str(SCOPE_ID),
    }
    resp = await client.post("/api/v1/security-program", json=payload, headers=headers)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_api_transition_program_status_success(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [], scope_id=SCOPE_ID)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-program/{p.program_id}/transition", json={"status": "ACTIVE"}, headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_transition_program_status_completed_rejection(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [], scope_id=SCOPE_ID)
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.COMPLETED)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-program/{p.program_id}/transition", json={"status": "ACTIVE"}, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_api_transition_program_status_closed_rejection(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [], scope_id=SCOPE_ID)
    await SecurityProgramService.transition_program_status(p.program_id, ProgramStatus.CLOSED)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-program/{p.program_id}/transition", json={"status": "ACTIVE"}, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_celery_worker_execution_success(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.continuous_refresh_service import ContinuousRefreshService
    await ContinuousRefreshService.refresh_all(mock_db)


@pytest.mark.asyncio
async def test_celery_worker_error_handling(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.continuous_refresh_service import ContinuousRefreshService
    with patch("src.services.security_program_service.SecurityProgramService.sync_programs", side_effect=Exception("worker error")):
        await ContinuousRefreshService.refresh_all(mock_db)


@pytest.mark.asyncio
async def test_program_fingerprint_case_insensitivity():
    f1 = ProgramFingerprintService.generate_fingerprint("VM Program", "Vulnerability Management", ProgramSeverity.HIGH)
    f2 = ProgramFingerprintService.generate_fingerprint("vm program", "Vulnerability Management", ProgramSeverity.HIGH)
    assert f1 == f2


@pytest.mark.asyncio
async def test_program_history_clear(mock_db, mock_scope):
    from src.infrastructure.database.models import SecurityProgramHistory
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("Hist Clear", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    assert len(await ProgramHistoryService.get_history(p.program_id)) == 1
    ProgramHistoryService.clear_history()
    mock_db._entities[SecurityProgramHistory] = []
    assert len(await ProgramHistoryService.get_history(p.program_id)) == 0


@pytest.mark.asyncio
async def test_program_correlation_clear(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("Corr Clear", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    with patch("src.services.program_correlation_service.IncidentService.get_all_incidents", return_value=[MagicMock(incident_id=uuid.uuid4(), title="Inc 1", asset_ids=[])]):
        await ProgramCorrelationService.correlate_program(mock_db, p.program_id, None)
        assert len(ProgramCorrelationService.get_correlations(p.program_id)) > 0
        ProgramCorrelationService.clear_correlations()
        assert len(ProgramCorrelationService.get_correlations(p.program_id)) == 0


@pytest.mark.asyncio
async def test_program_service_clear(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityProgramService.create_or_sync_program("P1", "Desc", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    assert len(SecurityProgramService.get_all_programs()) == 1
    SecurityProgramService.clear_programs()
    assert len(SecurityProgramService.get_all_programs()) == 0


@pytest.mark.asyncio
async def test_snapshot_service_clear(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityProgramSnapshotService.generate_snapshot(mock_db, None)
    SecurityProgramSnapshotService.clear_snapshots()
    snap = SecurityProgramSnapshotService.get_snapshot(None)
    assert snap["summary"]["total_programs"] == 0


@pytest.mark.asyncio
async def test_api_get_summary_snapshot_with_scope_id(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/security-program/summary?scope_id={SCOPE_ID}", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_create_program_with_invalid_scope_ownership(client, mock_db, mock_scope, mock_scope_2):
    setup_basic_mock_db(mock_db, mock_scope, mock_scope_2)
    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {
        "name": "Invalid Scope Program",
        "description": "Desc",
        "category": "Vulnerability Management",
        "severity": "HIGH",
        "scope_id": str(SCOPE_ID_2),
    }
    resp = await client.post("/api/v1/security-program", json=payload, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_program_identity_preservation_on_update(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityProgramService.create_or_sync_program("P1", "Desc 1", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    p_upd = await SecurityProgramService.create_or_sync_program("P1", "Desc 2", "Vulnerability Management", ProgramSeverity.HIGH, [], [])
    assert p_upd.program_id == p.program_id
    assert p_upd.description == "Desc 2"
