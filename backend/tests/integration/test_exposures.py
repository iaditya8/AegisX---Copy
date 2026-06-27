import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.core.security import create_access_token
from src.domain.entities.exposure import (
    ExposureSeverity,
    ExposureStatus,
    ExposureType,
    ExposureResponse,
)
from src.infrastructure.database.models import Asset, Finding, Scope, User, AssetPort
from src.services.exposure_type_registry import ExposureTypeRegistry
from src.services.exposure_severity_registry import ExposureSeverityRegistry
from src.services.attack_surface_registry import AttackSurfaceRegistry
from src.services.exposure_fingerprint_service import ExposureFingerprintService
from src.services.exposure_history_service import ExposureHistoryService
from src.services.exposure_prioritization_service import ExposurePrioritizationService
from src.services.exposure_correlation_service import ExposureCorrelationService
from src.services.attack_surface_service import AttackSurfaceService
from src.services.exposure_service import ExposureService
from src.services.exposure_drift_service import ExposureDriftService
from src.services.exposure_snapshot_service import ExposureSnapshotService
from src.services.ai_context_builder import AIContextBuilder
from src.services.ai_prompt_builder import AIPromptBuilder

ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OPERATOR_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
READER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SCOPE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
SCOPE_ID_2 = uuid.UUID("66666666-6666-6666-6666-666666666666")
ASSET_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")


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
    from src.services.alert_lifecycle_service import AlertLifecycleService
    from src.services.incident_service import IncidentService
    from src.services.case_service import CaseService
    from src.services.hunt_service import HuntService
    from src.services.purple_team_service import PurpleTeamService
    from src.services.purple_team_finding_service import PurpleTeamFindingService

    ExposureService.clear_exposures()
    ExposureHistoryService.clear_history()
    ExposureCorrelationService.clear_correlations()
    ExposureSnapshotService.clear_snapshots()
    AlertLifecycleService.clear_alerts()
    IncidentService.clear_incidents()
    CaseService.clear_cases()
    HuntService.clear_hunts()
    PurpleTeamService.clear_exercises()
    PurpleTeamFindingService.clear_findings()


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


def setup_test_db(mock_db, scopes=None, assets=None, findings=None, ports=None):
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    async def mock_get(model, ident):
        if model == Scope and scopes:
            for s in scopes:
                if s.id == ident:
                    return s
        if model == Finding and findings:
            for f in findings:
                if f.id == ident:
                    return f
        if model == Asset and assets:
            for a in assets:
                if a.id == ident:
                    return a
        return None

    mock_db.get = AsyncMock(side_effect=mock_get)

    async def mock_execute(query, *args, **kwargs):
        mock_result = MagicMock()
        query_str = str(query).lower()

        if "from scopes" in query_str or "from scope" in query_str:
            owner_id_val = None
            scope_id_val = None
            try:
                params = query.compile().params
                for k, v in params.items():
                    if isinstance(v, uuid.UUID) or (isinstance(v, str) and len(v) == 36):
                        val = uuid.UUID(str(v))
                        if any(s.id == val for s in (scopes or [])):
                            scope_id_val = val
                        else:
                            owner_id_val = val
            except Exception:
                pass

            filtered_scopes = scopes or []
            if scope_id_val:
                filtered_scopes = [s for s in filtered_scopes if s.id == scope_id_val]
            elif owner_id_val:
                filtered_scopes = [s for s in filtered_scopes if s.owner_id == owner_id_val]

            mock_result.scalar_one_or_none.side_effect = lambda: filtered_scopes[0] if filtered_scopes else None
            mock_result.scalars().all.side_effect = lambda: filtered_scopes
        elif "from assets" in query_str:
            mock_result.scalars().all.side_effect = lambda: assets or []
        elif "from findings" in query_str:
            mock_result.scalars().all.side_effect = lambda: findings or []
        elif "from asset_ports" in query_str:
            mock_result.scalars().all.side_effect = lambda: ports or []
        else:
            mock_result.scalar_one_or_none.side_effect = lambda: None
            mock_result.scalars().all.side_effect = lambda: []
        return mock_result

    mock_db.execute = AsyncMock(side_effect=mock_execute)


def setup_basic_mock_db(mock_db, mock_scope, mock_scope_2=None):
    scopes = [mock_scope]
    if mock_scope_2:
        scopes.append(mock_scope_2)
    
    asset = Asset()
    asset.id = ASSET_ID
    asset.scope_id = mock_scope.id
    asset.host = "test-host"
    asset.deleted_at = None
    
    setup_test_db(mock_db, scopes=scopes, assets=[asset])


# --- 1. Registries Tests (6 tests) ---

def test_exposure_type_valid():
    assert ExposureTypeRegistry.is_valid_type("MISCONFIGURATION") is True
    assert ExposureTypeRegistry.is_valid_type("EXPOSED_PORT") is True
    assert ExposureTypeRegistry.is_valid_type("INVALID") is False


def test_exposure_type_registered():
    registered = ExposureTypeRegistry.get_registered_types()
    assert ExposureType.MISCONFIGURATION in registered
    assert ExposureType.WEAK_CONTROL in registered


def test_exposure_severity_valid():
    resolved = ExposureSeverityRegistry.resolve_severity("CRITICAL")
    assert resolved == ExposureSeverity.CRITICAL


def test_exposure_severity_resolved():
    resolved = ExposureSeverityRegistry.resolve_severity("invalid")
    assert resolved == ExposureSeverity.LOW


def test_attack_surface_registry_valid():
    assert AttackSurfaceRegistry.is_valid_category("WEB_APPLICATION") is True
    assert AttackSurfaceRegistry.is_valid_category("INVALID") is False


def test_attack_surface_registry_categories():
    categories = AttackSurfaceRegistry.get_registered_categories()
    assert "WEB_APPLICATION" in categories
    assert "API" in categories


# --- 2. Fingerprinting & Stability Tests (3 tests) ---

def test_exposure_fingerprint_generation():
    fp1 = ExposureFingerprintService.generate_fingerprint(
        ExposureType.EXPOSED_PORT, ASSET_ID, "port:22"
    )
    fp2 = ExposureFingerprintService.generate_fingerprint(
        ExposureType.EXPOSED_PORT, ASSET_ID, "port:22"
    )
    assert fp1 == fp2


def test_exposure_fingerprint_stability():
    fp1 = ExposureFingerprintService.generate_fingerprint(
        ExposureType.EXPOSED_PORT, ASSET_ID, "port:22"
    )
    fp2 = ExposureFingerprintService.generate_fingerprint(
        ExposureType.EXPOSED_PORT, ASSET_ID, "  port:22  "
    )
    assert fp1 == fp2


@pytest.mark.asyncio
async def test_exposure_sync_preserves_identity(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    exp1 = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    exp2 = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc 2", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    assert exp1.exposure_id == exp2.exposure_id
    assert exp2.description == "Desc 2"


# --- 3. Exposure History Logs Tests (4 tests) ---

def test_history_empty():
    assert len(ExposureHistoryService.get_history(uuid.uuid4())) == 0


def test_history_record_event():
    exp_id = uuid.uuid4()
    entry = ExposureHistoryService.record_event(exp_id, "CREATED", "Created exposure")
    assert entry.exposure_id == exp_id
    assert entry.event_type == "CREATED"


def test_history_clear():
    exp_id = uuid.uuid4()
    ExposureHistoryService.record_event(exp_id, "CREATED", "Created")
    ExposureHistoryService.clear_history()
    assert len(ExposureHistoryService.get_history(exp_id)) == 0


def test_history_preserved():
    exp_id = uuid.uuid4()
    ExposureHistoryService.record_event(exp_id, "CREATED", "Created")
    hist = ExposureHistoryService.get_history(exp_id)
    assert len(hist) == 1
    assert hist[0].event_type == "CREATED"


# --- 4. Prioritization Service Tests (4 tests) ---

@pytest.mark.asyncio
async def test_prioritization_critical(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    res = await ExposurePrioritizationService.calculate_exposure_priority(
        mock_db, ASSET_ID, ExposureSeverity.CRITICAL
    )
    assert res["likelihood"] == 0.9
    assert res["risk_score"] > 0.0


@pytest.mark.asyncio
async def test_prioritization_high(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    res = await ExposurePrioritizationService.calculate_exposure_priority(
        mock_db, ASSET_ID, ExposureSeverity.HIGH
    )
    assert res["likelihood"] == 0.7


@pytest.mark.asyncio
async def test_prioritization_medium(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    res = await ExposurePrioritizationService.calculate_exposure_priority(
        mock_db, ASSET_ID, ExposureSeverity.MEDIUM
    )
    assert res["likelihood"] == 0.5


@pytest.mark.asyncio
async def test_prioritization_low(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    res = await ExposurePrioritizationService.calculate_exposure_priority(
        mock_db, ASSET_ID, ExposureSeverity.LOW
    )
    assert res["likelihood"] == 0.3


# --- 5. Correlation Service Tests (7 tests) ---

@pytest.mark.asyncio
async def test_correlation_empty(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    res = await ExposureCorrelationService.correlate_exposure(mock_db, uuid.uuid4(), ASSET_ID)
    assert len(res) == 0


@pytest.mark.asyncio
async def test_correlation_findings(mock_db):
    finding = Finding()
    finding.id = uuid.uuid4()
    finding.asset_id = ASSET_ID
    finding.title = "Vulnerable library"
    setup_test_db(mock_db, findings=[finding])
    res = await ExposureCorrelationService.correlate_exposure(mock_db, uuid.uuid4(), ASSET_ID)
    assert len(res) == 1
    assert res[0]["entity_type"] == "Finding"


@pytest.mark.asyncio
async def test_correlation_alerts(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.alert_lifecycle_service import AlertLifecycleService
    alert = MagicMock(alert_id=uuid.uuid4(), asset_id=ASSET_ID, title="Alert 1")
    
    with patch.object(AlertLifecycleService, "get_all_alerts", return_value=[alert]):
        res = await ExposureCorrelationService.correlate_exposure(mock_db, uuid.uuid4(), ASSET_ID)
        assert len(res) == 1
        assert res[0]["entity_type"] == "Alert"


@pytest.mark.asyncio
async def test_correlation_incidents(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.incident_service import IncidentService
    incident = MagicMock(incident_id=uuid.uuid4(), asset_ids=[ASSET_ID], title="Incident 1")
    
    with patch.object(IncidentService, "get_all_incidents", return_value=[incident]):
        res = await ExposureCorrelationService.correlate_exposure(mock_db, uuid.uuid4(), ASSET_ID)
        assert len(res) == 1
        assert res[0]["entity_type"] == "Incident"


@pytest.mark.asyncio
async def test_correlation_cases(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.case_service import CaseService
    case = MagicMock(case_id=uuid.uuid4(), asset_ids=[ASSET_ID], title="Case 1")
    
    with patch.object(CaseService, "get_all_cases", return_value=[case]):
        res = await ExposureCorrelationService.correlate_exposure(mock_db, uuid.uuid4(), ASSET_ID)
        assert len(res) == 1
        assert res[0]["entity_type"] == "Case"


@pytest.mark.asyncio
async def test_correlation_hunts(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.hunt_service import HuntService
    hunt = MagicMock(
        hunt_id=uuid.uuid4(),
        related_entities=[{"entity_id": str(ASSET_ID)}],
        title="Hunt 1"
    )
    
    with patch.object(HuntService, "get_all_hunts", return_value=[hunt]):
        res = await ExposureCorrelationService.correlate_exposure(mock_db, uuid.uuid4(), ASSET_ID)
        assert len(res) == 1
        assert res[0]["entity_type"] == "Hunt"


@pytest.mark.asyncio
async def test_correlation_purple_team(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.purple_team_service import PurpleTeamService
    from src.services.purple_team_finding_service import PurpleTeamFindingService
    exercise = MagicMock(
        exercise_id=uuid.uuid4(),
        related_entities=[{"entity_id": str(ASSET_ID)}]
    )
    finding = MagicMock(finding_id=uuid.uuid4(), description="Purple Team finding")
    
    with patch.object(PurpleTeamService, "get_all_exercises", return_value=[exercise]), \
         patch.object(PurpleTeamFindingService, "get_findings", return_value=[finding]):
        res = await ExposureCorrelationService.correlate_exposure(mock_db, uuid.uuid4(), ASSET_ID)
        assert len(res) == 1
        assert res[0]["entity_type"] == "PurpleTeamFinding"


# --- 6. Attack Surface Service Tests (6 tests) ---

@pytest.mark.asyncio
async def test_attack_surface_mapping_web(mock_db):
    port = AssetPort()
    port.asset_id = ASSET_ID
    port.port = 443
    port.protocol = "tcp"
    port.state = "open"
    setup_test_db(mock_db, ports=[port])
    cats = await AttackSurfaceService.get_asset_categories(mock_db, ASSET_ID)
    assert "WEB_APPLICATION" in cats


@pytest.mark.asyncio
async def test_attack_surface_mapping_api(mock_db):
    port = AssetPort()
    port.asset_id = ASSET_ID
    port.port = 8080
    port.protocol = "tcp"
    port.state = "open"
    setup_test_db(mock_db, ports=[port])
    cats = await AttackSurfaceService.get_asset_categories(mock_db, ASSET_ID)
    assert "API" in cats


@pytest.mark.asyncio
async def test_attack_surface_mapping_host(mock_db):
    port = AssetPort()
    port.asset_id = ASSET_ID
    port.port = 22
    port.protocol = "tcp"
    port.state = "open"
    setup_test_db(mock_db, ports=[port])
    cats = await AttackSurfaceService.get_asset_categories(mock_db, ASSET_ID)
    assert "HOST" in cats


@pytest.mark.asyncio
async def test_attack_surface_mapping_email(mock_db):
    port = AssetPort()
    port.asset_id = ASSET_ID
    port.port = 25
    port.protocol = "tcp"
    port.state = "open"
    setup_test_db(mock_db, ports=[port])
    cats = await AttackSurfaceService.get_asset_categories(mock_db, ASSET_ID)
    assert "EMAIL" in cats


@pytest.mark.asyncio
async def test_attack_surface_mapping_identity(mock_db):
    port = AssetPort()
    port.asset_id = ASSET_ID
    port.port = 389
    port.protocol = "tcp"
    port.state = "open"
    setup_test_db(mock_db, ports=[port])
    cats = await AttackSurfaceService.get_asset_categories(mock_db, ASSET_ID)
    assert "IDENTITY" in cats


@pytest.mark.asyncio
async def test_attack_surface_mapping_network(mock_db):
    port = AssetPort()
    port.asset_id = ASSET_ID
    port.port = 21
    port.protocol = "tcp"
    port.state = "open"
    setup_test_db(mock_db, ports=[port])
    cats = await AttackSurfaceService.get_asset_categories(mock_db, ASSET_ID)
    assert "NETWORK_SERVICE" in cats


# --- 7. Exposure Service & Lifecycle Transitions (7 tests) ---

@pytest.mark.asyncio
async def test_exposure_auto_creation(mock_db):
    # Setup asset and finding
    asset = Asset()
    asset.id = ASSET_ID
    asset.host = "test-host"
    asset.deleted_at = None
    finding = Finding()
    finding.id = uuid.uuid4()
    finding.asset_id = ASSET_ID
    finding.severity = "high"
    finding.title = "Weak cipher"
    setup_test_db(mock_db, assets=[asset], findings=[finding])

    res = await ExposureService.sync_exposures(mock_db)
    assert len(res) == 1
    assert res[0].exposure_type == ExposureType.MISCONFIGURATION


@pytest.mark.asyncio
async def test_exposure_validate_transition(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    validated = ExposureService.validate_exposure(exp.exposure_id)
    assert validated.status == ExposureStatus.VALIDATED


@pytest.mark.asyncio
async def test_exposure_accept_transition(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    ExposureService.validate_exposure(exp.exposure_id)
    accepted = ExposureService.accept_exposure(exp.exposure_id)
    assert accepted.status == ExposureStatus.ACCEPTED


@pytest.mark.asyncio
async def test_exposure_mitigate_transition(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    ExposureService.validate_exposure(exp.exposure_id)
    mitigated = ExposureService.mitigate_exposure(exp.exposure_id)
    assert mitigated.status == ExposureStatus.MITIGATED


@pytest.mark.asyncio
async def test_exposure_close_transition(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    ExposureService.validate_exposure(exp.exposure_id)
    ExposureService.mitigate_exposure(exp.exposure_id)
    closed = ExposureService.close_exposure(exp.exposure_id)
    assert closed.status == ExposureStatus.CLOSED


@pytest.mark.asyncio
async def test_exposure_terminal_state_enforcement(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    ExposureService.validate_exposure(exp.exposure_id)
    ExposureService.mitigate_exposure(exp.exposure_id)
    ExposureService.close_exposure(exp.exposure_id)

    with pytest.raises(ValueError):
        ExposureService.validate_exposure(exp.exposure_id)


@pytest.mark.asyncio
async def test_exposure_invalid_transitions(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    with pytest.raises(ValueError):
        ExposureService.close_exposure(exp.exposure_id)


# --- 8. Drift Detection Tests (5 tests) ---

@pytest.mark.asyncio
async def test_drift_new_exposure(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.workflow_event_service import WorkflowEventService
    
    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    prev_snapshot = {"exposures": {}, "attack_surface": {}}
    
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await ExposureDriftService.check_drift(mock_db, SCOPE_ID, prev_snapshot)
        assert mock_emit.call_count >= 1


@pytest.mark.asyncio
async def test_drift_exposure_removed(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.workflow_event_service import WorkflowEventService

    prev_snapshot = {
        "exposures": {
            "some-id": {
                "exposure_fingerprint": "prev-fingerprint",
                "title": "Old Exp",
                "severity": "HIGH",
                "risk_score": 50.0,
            }
        },
        "attack_surface": {}
    }
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await ExposureDriftService.check_drift(mock_db, SCOPE_ID, prev_snapshot)
        assert mock_emit.call_count >= 1


@pytest.mark.asyncio
async def test_drift_severity_changed(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.workflow_event_service import WorkflowEventService

    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    prev_snapshot = {
        "exposures": {
            str(exp.exposure_id): {
                "exposure_fingerprint": exp.exposure_fingerprint,
                "title": exp.title,
                "severity": "LOW",
                "risk_score": exp.risk_score,
            }
        },
        "attack_surface": {}
    }
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await ExposureDriftService.check_drift(mock_db, SCOPE_ID, prev_snapshot)
        assert mock_emit.call_count >= 1


@pytest.mark.asyncio
async def test_drift_priority_changed(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.workflow_event_service import WorkflowEventService

    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    prev_snapshot = {
        "exposures": {
            str(exp.exposure_id): {
                "exposure_fingerprint": exp.exposure_fingerprint,
                "title": exp.title,
                "severity": exp.severity.value,
                "risk_score": 10.0,
            }
        },
        "attack_surface": {}
    }
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await ExposureDriftService.check_drift(mock_db, SCOPE_ID, prev_snapshot)
        assert mock_emit.call_count >= 1


@pytest.mark.asyncio
async def test_drift_attack_surface_changed(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.workflow_event_service import WorkflowEventService

    prev_snapshot = {
        "exposures": {},
        "attack_surface": {
            str(ASSET_ID): ["EMAIL"]
        }
    }
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await ExposureDriftService.check_drift(mock_db, SCOPE_ID, prev_snapshot)
        assert mock_emit.call_count >= 1


# --- 9. Snapshot & Cache Rebuild Tests (3 tests) ---

@pytest.mark.asyncio
async def test_snapshot_rebuild_consistency(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    snap1 = await ExposureSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    assert snap1["summary"]["total_exposures"] == 1


@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_deletion(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    await ExposureSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    ExposureSnapshotService.clear_snapshots()
    snap = ExposureSnapshotService.get_snapshot(SCOPE_ID)
    assert snap["summary"]["total_exposures"] == 0


@pytest.mark.asyncio
async def test_snapshot_rebuild_after_corruption(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    ExposureSnapshotService._snapshots[SCOPE_ID] = {"corrupted": True}
    snap = await ExposureSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    assert "summary" in snap
    assert "corrupted" not in snap


# --- 10. AI Context & Advisory Prompt Constraints (2 tests) ---

@pytest.mark.asyncio
async def test_ai_context_exposure_injection(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    await ExposureSnapshotService.generate_snapshot(mock_db, SCOPE_ID)

    from src.services.asset_report_service import AssetReportService
    mock_report = {
        "asset": {"id": str(ASSET_ID), "scope_id": SCOPE_ID},
        "risk": {},
        "findings": [],
        "exposure": {}
    }

    with patch.object(AssetReportService, "generate_asset_report", new_callable=AsyncMock, return_value=mock_report):
        ctx = await AIContextBuilder.build_asset_context(mock_db, ASSET_ID)
        assert "exposure_summary" in ctx["asset"]
        assert "active_exposures" in ctx["asset"]
        assert "attack_surface_inventory" in ctx["asset"]


def test_ai_advisory_only_enforcement():
    context = {"dummy": "data"}
    prompt = AIPromptBuilder.build_asset_prompt(context)
    assert "exposures" in prompt
    assert "validating, accepting, mitigating, closing" in prompt


# --- 11. REST API Routing Tests (14 tests) ---

@pytest.mark.asyncio
async def test_api_list_exposures(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/exposures", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_api_list_open_exposures(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/exposures/open", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_api_list_critical_exposures(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.CRITICAL, ASSET_ID, "port:22"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/exposures/critical", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_api_get_exposure(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/exposures/{exp.exposure_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "Title"


@pytest.mark.asyncio
async def test_api_create_exposure(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {
        "title": "API Exp",
        "description": "Via API",
        "exposure_type": "EXPOSED_PORT",
        "severity": "HIGH",
        "asset_id": str(ASSET_ID),
        "target": "port:80",
    }
    resp = await client.post("/api/v1/exposures", json=payload, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["data"]["title"] == "API Exp"


@pytest.mark.asyncio
async def test_api_validate_exposure(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/exposures/{exp.exposure_id}/validate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "VALIDATED"


@pytest.mark.asyncio
async def test_api_accept_exposure(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    await client.post(f"/api/v1/exposures/{exp.exposure_id}/validate", headers=headers)
    resp = await client.post(f"/api/v1/exposures/{exp.exposure_id}/accept", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_api_mitigate_exposure(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    await client.post(f"/api/v1/exposures/{exp.exposure_id}/validate", headers=headers)
    resp = await client.post(f"/api/v1/exposures/{exp.exposure_id}/mitigate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "MITIGATED"


@pytest.mark.asyncio
async def test_api_close_exposure(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    await client.post(f"/api/v1/exposures/{exp.exposure_id}/validate", headers=headers)
    await client.post(f"/api/v1/exposures/{exp.exposure_id}/mitigate", headers=headers)
    resp = await client.post(f"/api/v1/exposures/{exp.exposure_id}/close", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_api_rbac_permissions(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, ASSET_ID, "port:22"
    )
    headers = get_auth_header(READER_ID, "reader")
    resp = await client.post(f"/api/v1/exposures/{exp.exposure_id}/validate", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_rbac_reader_restrictions(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(READER_ID, "reader")
    payload = {
        "title": "API Exp",
        "description": "Via API",
        "exposure_type": "EXPOSED_PORT",
        "severity": "HIGH",
        "asset_id": str(ASSET_ID),
        "target": "port:80",
    }
    resp = await client.post("/api/v1/exposures", json=payload, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_rbac_scope_validation(client, mock_db, mock_scope, mock_scope_2):
    setup_basic_mock_db(mock_db, mock_scope, mock_scope_2)
    # create exposure in scope_2 which operator does not own
    asset_other = Asset()
    asset_other.id = uuid.uuid4()
    asset_other.scope_id = mock_scope_2.id
    asset_other.host = "other-host"
    asset_other.deleted_at = None
    setup_test_db(mock_db, scopes=[mock_scope, mock_scope_2], assets=[asset_other])

    exp = await ExposureService.create_or_sync_exposure(
        mock_db, "Title", "Desc", ExposureType.EXPOSED_PORT, ExposureSeverity.HIGH, asset_other.id, "port:22"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/exposures/{exp.exposure_id}", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_drift_check(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/exposures/drift", headers=headers)
    assert resp.status_code == 200
    assert "snapshot" in resp.json()["data"]


@pytest.mark.asyncio
async def test_api_summary(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/exposures/summary", headers=headers)
    assert resp.status_code == 200
