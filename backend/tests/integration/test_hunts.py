import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.core.security import create_access_token
from src.domain.entities.hunt import HuntSeverity, HuntStatus, HuntType, HuntResponse
from src.domain.entities.threat_intelligence import IOCType, IOCSeverity, IOCStatus, ThreatFeedType
from src.infrastructure.database.models import Asset, Finding, Scope, User
from src.services.hunt_type_registry import HuntTypeRegistry
from src.services.hunt_severity_registry import HuntSeverityRegistry
from src.services.hunt_fingerprint_service import HuntFingerprintService
from src.services.hunt_history_service import HuntHistoryService
from src.services.hunt_hypothesis_service import HuntHypothesisService
from src.services.hunt_finding_service import HuntFindingService
from src.services.hunt_service import HuntService, HuntRecord
from src.services.ioc_service import IOCService
from src.services.ioc_correlation_service import IOCCorrelationService, IOCCorrelationRecord
from src.services.detection_service import DetectionService, DetectionRecord
from src.domain.entities.detection import DetectionSeverity, DetectionStatus
from src.services.detection_coverage_service import DetectionCoverageService
from src.services.ioc_hunt_service import IOCHuntService
from src.services.attack_hunt_service import AttackHuntService
from src.services.hunt_coverage_service import HuntCoverageService
from src.services.hunt_drift_service import HuntDriftService
from src.services.hunt_snapshot_service import HuntSnapshotService
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
    HuntService.clear_hunts()
    HuntHistoryService.clear_history()
    HuntHypothesisService.clear_hypotheses()
    HuntFindingService.clear_findings()
    HuntSnapshotService.clear_snapshots()
    IOCService.clear_iocs()
    IOCCorrelationService.clear_correlations()
    DetectionService.clear_detections()


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


def setup_test_db(mock_db, scopes=None, assets=None, findings=None, workflow=None):
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

        # Scopes query
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
        # Assets query
        elif "from assets" in query_str:
            mock_result.scalars().all.side_effect = lambda: assets or []
        # Findings query
        elif "from findings" in query_str:
            mock_result.scalars().all.side_effect = lambda: findings or []
        # Workflows query
        elif "from workflows" in query_str:
            mock_result.scalar_one_or_none.side_effect = lambda: workflow
            mock_result.scalars().all.side_effect = lambda: [workflow] if workflow else []
        else:
            mock_result.scalar_one_or_none.side_effect = lambda: None
            mock_result.scalars().all.side_effect = lambda: []
        return mock_result

    mock_db.execute = AsyncMock(side_effect=mock_execute)


def setup_basic_mock_db(mock_db, mock_scope, mock_scope_2=None):
    scopes = [mock_scope]
    if mock_scope_2:
        scopes.append(mock_scope_2)
    setup_test_db(mock_db, scopes=scopes)


# --- 1. Hunt Type & Severity Registry Tests (6 tests) ---

def test_hunt_type_valid():
    assert HuntTypeRegistry.is_valid_type("IOC_DRIVEN") is True
    assert HuntTypeRegistry.is_valid_type("ATTACK_DRIVEN") is True
    assert HuntTypeRegistry.is_valid_type("INVALID_TYPE") is False


def test_hunt_type_registered():
    registered = HuntTypeRegistry.get_registered_types()
    assert HuntType.IOC_DRIVEN in registered
    assert HuntType.MANUAL in registered


def test_hunt_severity_resolve():
    assert HuntSeverityRegistry.resolve_severity("critical") == HuntSeverity.CRITICAL
    assert HuntSeverityRegistry.resolve_severity("MEDIUM") == HuntSeverity.MEDIUM
    assert HuntSeverityRegistry.resolve_severity("INVALID") == HuntSeverity.LOW


def test_hunt_highest_severity():
    sevs = [HuntSeverity.LOW, HuntSeverity.CRITICAL, HuntSeverity.MEDIUM]
    assert HuntSeverityRegistry.get_highest_severity(sevs) == HuntSeverity.CRITICAL


def test_hunt_highest_severity_empty():
    assert HuntSeverityRegistry.get_highest_severity([]) == HuntSeverity.LOW


def test_hunt_highest_severity_strings():
    sevs = ["low", "high", "medium"]
    assert HuntSeverityRegistry.get_highest_severity(sevs) == HuntSeverity.HIGH


# --- 2. Hunt Fingerprint Stability Tests (3 tests) ---

def test_hunt_fingerprint_generation():
    ent = [{"entity_type": "IOC", "entity_id": "123"}]
    fp1 = HuntFingerprintService.generate_fingerprint(HuntType.IOC_DRIVEN, "Title", ent)
    fp2 = HuntFingerprintService.generate_fingerprint(HuntType.IOC_DRIVEN, "title ", ent)
    assert fp1 == fp2


def test_hunt_fingerprint_sorted_entities():
    ent1 = [{"entity_type": "IOC", "entity_id": "1"}, {"entity_type": "Asset", "entity_id": "2"}]
    ent2 = [{"entity_type": "Asset", "entity_id": "2"}, {"entity_type": "IOC", "entity_id": "1"}]
    fp1 = HuntFingerprintService.generate_fingerprint(HuntType.IOC_DRIVEN, "Title", ent1)
    fp2 = HuntFingerprintService.generate_fingerprint(HuntType.IOC_DRIVEN, "Title", ent2)
    assert fp1 == fp2


def test_hunt_fingerprint_changes():
    ent = [{"entity_type": "IOC", "entity_id": "123"}]
    fp1 = HuntFingerprintService.generate_fingerprint(HuntType.IOC_DRIVEN, "Title A", ent)
    fp2 = HuntFingerprintService.generate_fingerprint(HuntType.IOC_DRIVEN, "Title B", ent)
    assert fp1 != fp2


# --- 3. Hunt Lifecycle, Sync, and terminal status Tests (10 tests) ---

def test_hunt_creation():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    assert hunt.title == "Test Hunt"
    assert hunt.status == HuntStatus.OPEN
    assert len(HuntService.get_all_hunts()) == 1


def test_hunt_sync_preserves_identity():
    hunt1 = HuntService.create_or_sync_hunt("Test Hunt", "Desc 1", HuntType.MANUAL, HuntSeverity.HIGH)
    hunt2 = HuntService.create_or_sync_hunt("Test Hunt", "Desc 2", HuntType.MANUAL, HuntSeverity.CRITICAL)
    assert hunt1.hunt_id == hunt2.hunt_id
    assert hunt2.description == "Desc 2"
    assert hunt2.severity == HuntSeverity.CRITICAL


def test_hunt_sync_preserves_status():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    HuntService.activate_hunt(hunt.hunt_id)
    synced = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    assert synced.status == HuntStatus.ACTIVE


def test_hunt_activate_transition():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    HuntService.activate_hunt(hunt.hunt_id, user_id=ADMIN_ID)
    assert hunt.status == HuntStatus.ACTIVE
    assert hunt.owner_id == ADMIN_ID


def test_hunt_review_transition():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    HuntService.review_hunt(hunt.hunt_id)
    assert hunt.status == HuntStatus.UNDER_REVIEW


def test_hunt_complete_transition():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    HuntService.complete_hunt(hunt.hunt_id)
    assert hunt.status == HuntStatus.COMPLETED


def test_hunt_close_transition():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    HuntService.close_hunt(hunt.hunt_id)
    assert hunt.status == HuntStatus.CLOSED


def test_hunt_escalate_transition():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    HuntService.escalate_hunt(hunt.hunt_id)
    assert hunt.status == HuntStatus.ESCALATED


def test_hunt_terminal_state_enforcement():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    HuntService.close_hunt(hunt.hunt_id)
    with pytest.raises(ValueError, match="terminal state"):
        HuntService.activate_hunt(hunt.hunt_id)


def test_hunt_terminal_state_enforcement_sync():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    HuntService.close_hunt(hunt.hunt_id)
    synced = HuntService.create_or_sync_hunt("Test Hunt", "Desc New", HuntType.MANUAL, HuntSeverity.HIGH)
    assert synced.status == HuntStatus.CLOSED


# --- 4. Hunt History & Audit Trails (3 tests) ---

def test_hunt_history_recording():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    HuntService.activate_hunt(hunt.hunt_id)
    history = HuntHistoryService.get_history(hunt.hunt_id)
    assert len(history) == 2
    assert history[0].event_type == "CREATED"
    assert history[1].event_type == "ACTIVATED"


def test_hunt_history_immutable():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    history = HuntHistoryService.get_history(hunt.hunt_id)
    from pydantic import ValidationError
    with pytest.raises((TypeError, ValidationError)):
        history[0].details = "Malicious update"  # type: ignore


def test_hunt_history_survives_sync():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    HuntService.create_or_sync_hunt("Test Hunt", "Desc New", HuntType.MANUAL, HuntSeverity.HIGH)
    history = HuntHistoryService.get_history(hunt.hunt_id)
    assert len(history) == 2
    assert history[0].event_type == "CREATED"
    assert history[1].event_type == "UPDATED"


# --- 5. Hypotheses & Findings tracking (6 tests) ---

def test_hypothesis_creation():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    hyp = HuntHypothesisService.create_hypothesis(hunt.hunt_id, "Hypothesis 1")
    assert hyp.description == "Hypothesis 1"
    assert len(HuntHypothesisService.get_hypotheses(hunt.hunt_id)) == 1


def test_hypothesis_preservation_on_sync():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    HuntHypothesisService.create_hypothesis(hunt.hunt_id, "Hypothesis 1")
    HuntService.create_or_sync_hunt("Test Hunt", "Desc New", HuntType.MANUAL, HuntSeverity.HIGH)
    assert len(HuntHypothesisService.get_hypotheses(hunt.hunt_id)) == 1


def test_finding_creation():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    finding = HuntFindingService.create_finding(hunt.hunt_id, "Asset", uuid.uuid4(), "Finding 1")
    assert finding.details == "Finding 1"
    assert len(HuntFindingService.get_findings(hunt.hunt_id)) == 1


def test_finding_duplicate_prevention():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    asset_id = uuid.uuid4()
    HuntFindingService.create_finding(hunt.hunt_id, "Asset", asset_id, "Finding 1")
    HuntFindingService.create_finding(hunt.hunt_id, "Asset", asset_id, "Finding 2")
    assert len(HuntFindingService.get_findings(hunt.hunt_id)) == 1


def test_finding_preservation_on_sync():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    HuntFindingService.create_finding(hunt.hunt_id, "Asset", uuid.uuid4(), "Finding 1")
    HuntService.create_or_sync_hunt("Test Hunt", "Desc New", HuntType.MANUAL, HuntSeverity.HIGH)
    assert len(HuntFindingService.get_findings(hunt.hunt_id)) == 1


def test_hunt_to_response():
    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    HuntHypothesisService.create_hypothesis(hunt.hunt_id, "Hypothesis 1")
    HuntFindingService.create_finding(hunt.hunt_id, "Asset", uuid.uuid4(), "Finding 1")
    resp = HuntService.to_response(hunt)
    assert isinstance(resp, HuntResponse)
    assert len(resp.hypotheses) == 1
    assert len(resp.findings) == 1


# --- 6. IOC Hunt Auto-generation (3 tests) ---

def test_ioc_hunt_generation():
    # Setup correlated IOC
    ioc = IOCService.create_or_sync_ioc(
        value="1.1.1.1",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.HIGH,
        reputation=85,
        feed_type=ThreatFeedType.COMMUNITY,
    )
    correlation_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    corr_record = IOCCorrelationRecord(
        correlation_id=correlation_id,
        ioc_id=ioc.ioc_id,
        ioc_fingerprint=ioc.ioc_fingerprint,
        entity_type="Asset",
        entity_id=entity_id,
        scope_id=None,
    )
    IOCCorrelationService._correlations[correlation_id] = corr_record

    IOCHuntService.sync_ioc_hunts()

    hunts = HuntService.get_all_hunts()
    assert len(hunts) == 1
    assert hunts[0].hunt_type == HuntType.IOC_DRIVEN
    assert hunts[0].severity == HuntSeverity.HIGH


def test_ioc_hunt_generation_hypothesis_and_findings():
    ioc = IOCService.create_or_sync_ioc(
        value="1.1.1.1",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.HIGH,
        reputation=85,
        feed_type=ThreatFeedType.COMMUNITY,
    )
    correlation_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    corr_record = IOCCorrelationRecord(
        correlation_id=correlation_id,
        ioc_id=ioc.ioc_id,
        ioc_fingerprint=ioc.ioc_fingerprint,
        entity_type="Asset",
        entity_id=entity_id,
        scope_id=None,
    )
    IOCCorrelationService._correlations[correlation_id] = corr_record

    IOCHuntService.sync_ioc_hunts()
    hunts = HuntService.get_all_hunts()
    resp = HuntService.to_response(hunts[0])
    assert len(resp.hypotheses) == 1
    assert "1.1.1.1" in resp.hypotheses[0].description
    assert len(resp.findings) == 1
    assert resp.findings[0].entity_type == "Asset"
    assert resp.findings[0].entity_id == entity_id


def test_ioc_hunt_generation_no_correlation():
    IOCService.create_or_sync_ioc(
        value="1.1.1.1",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.HIGH,
        reputation=85,
        feed_type=ThreatFeedType.COMMUNITY,
    )
    IOCHuntService.sync_ioc_hunts()
    assert len(HuntService.get_all_hunts()) == 0


# --- 7. ATT&CK Hunt Auto-generation (3 tests) ---

@pytest.mark.asyncio
async def test_attack_hunt_generation():
    mock_db = AsyncMock()
    setup_test_db(mock_db)

    # Preseed techniques to register them in AttackRegistry
    from src.services.attack_registry import AttackRegistry
    # We have T1059 pre-seeded in the system

    # Setup detections (none active or present) so technique is NOT_COVERED
    DetectionService.clear_detections()

    await AttackHuntService.sync_attack_hunts(mock_db)
    hunts = HuntService.get_all_hunts()
    assert len(hunts) > 0
    # Should contain T1059 detection gap hunt
    t1059_hunt = [h for h in hunts if "T1059" in h.title]
    assert len(t1059_hunt) == 1
    assert t1059_hunt[0].hunt_type == HuntType.DETECTION_GAP
    assert t1059_hunt[0].severity == HuntSeverity.HIGH


@pytest.mark.asyncio
async def test_attack_hunt_generation_partial_coverage():
    mock_db = AsyncMock()
    setup_test_db(mock_db)

    # Seed detection rule that is DISABLED/DEPRECATED
    DetectionService.clear_detections()
    det = DetectionService.create_or_sync_detection(
        name="Disabled Rule",
        description="...",
        severity=DetectionSeverity.MEDIUM,
        attack_techniques=["T1059"],
    )
    det.status = DetectionStatus.DISABLED

    await AttackHuntService.sync_attack_hunts(mock_db)
    hunts = HuntService.get_all_hunts()
    t1059_hunt = [h for h in hunts if "T1059" in h.title]
    assert len(t1059_hunt) == 1
    assert t1059_hunt[0].hunt_type == HuntType.ATTACK_DRIVEN
    assert t1059_hunt[0].severity == HuntSeverity.MEDIUM


@pytest.mark.asyncio
async def test_attack_hunt_generation_correlation_findings():
    mock_db = AsyncMock()
    finding = Finding()
    finding.id = uuid.uuid4()
    finding.title = "Suspicious process execution T1059"
    finding.description = "..."
    finding.metadata_json = {}
    setup_test_db(mock_db, findings=[finding])

    await AttackHuntService.sync_attack_hunts(mock_db)
    hunts = HuntService.get_all_hunts()
    t1059_hunt = [h for h in hunts if "T1059" in h.title]
    assert len(t1059_hunt) == 1
    resp = HuntService.to_response(t1059_hunt[0])
    assert len(resp.findings) == 1
    assert resp.findings[0].entity_id == finding.id


# --- 8. Hunt Coverage Calculations (3 tests) ---

def test_hunt_coverage_empty():
    cov = HuntCoverageService.calculate_coverage()
    assert cov["attack_coverage"] == 0.0
    assert cov["ioc_coverage"] == 100.0


def test_hunt_coverage_active():
    # Seed covered technique
    det = DetectionService.create_or_sync_detection(
        name="Active Rule",
        description="...",
        severity=DetectionSeverity.MEDIUM,
        attack_techniques=["T1059", "T1562", "T1078", "T1027", "T1105", "T1047", "T1055"],
    )
    det.status = DetectionStatus.ACTIVE
    # Seed active & expired IOCs
    IOCService.create_or_sync_ioc("1.1.1.1", IOCType.IP_ADDRESS, IOCSeverity.HIGH, 90, ThreatFeedType.INTERNAL)
    ioc2 = IOCService.create_or_sync_ioc("2.2.2.2", IOCType.IP_ADDRESS, IOCSeverity.HIGH, 90, ThreatFeedType.INTERNAL)
    IOCService.expire_ioc(ioc2.ioc_id)

    cov = HuntCoverageService.calculate_coverage()
    assert cov["attack_coverage"] == 100.0
    assert cov["ioc_coverage"] == 50.0


def test_actor_campaign_coverage():
    # Seed active IOC with actors/campaigns
    IOCService.create_or_sync_ioc(
        value="3.3.3.3",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.HIGH,
        reputation=90,
        feed_type=ThreatFeedType.INTERNAL,
        threat_actors=["Lazarus"],
        campaigns=["Operation Ghost"],
    )
    cov = HuntCoverageService.calculate_coverage()
    assert cov["actor_coverage"] > 0.0
    assert cov["campaign_coverage"] > 0.0


# --- 9. Hunt Drift Detection (4 tests) ---

@pytest.mark.asyncio
async def test_hunt_drift_no_previous():
    mock_db = AsyncMock()
    setup_test_db(mock_db)
    await HuntDriftService.check_drift(mock_db, prev_snapshot=None)
    assert not mock_db.add.called


@pytest.mark.asyncio
async def test_hunt_drift_status_change():
    mock_db = AsyncMock()
    mock_wf = MagicMock()
    mock_wf.id = uuid.uuid4()
    setup_test_db(mock_db, workflow=mock_wf)

    hunt = HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    prev_snap = HuntSnapshotService.generate_snapshot()

    # Change status
    HuntService.activate_hunt(hunt.hunt_id)

    await HuntDriftService.check_drift(mock_db, prev_snapshot=prev_snap)
    assert mock_db.add.called
    events = [call_arg[0][0].event_type for call_arg in mock_db.add.call_args_list]
    assert "hunt.drift" in events


@pytest.mark.asyncio
async def test_hunt_drift_coverage_change():
    mock_db = AsyncMock()
    mock_wf = MagicMock()
    mock_wf.id = uuid.uuid4()
    setup_test_db(mock_db, workflow=mock_wf)

    # Rebuild snapshot with initial coverage
    prev_snap = HuntSnapshotService.generate_snapshot()

    # Trigger change in coverage
    IOCService.create_or_sync_ioc("1.1.1.1", IOCType.IP_ADDRESS, IOCSeverity.HIGH, 90, ThreatFeedType.INTERNAL, threat_actors=["Lazarus"])

    await HuntDriftService.check_drift(mock_db, prev_snapshot=prev_snap)
    assert mock_db.add.called
    events = [call_arg[0][0].event_type for call_arg in mock_db.add.call_args_list]
    assert "hunt.coverage_changed" in events


@pytest.mark.asyncio
async def test_hunt_drift_no_change():
    mock_db = AsyncMock()
    setup_test_db(mock_db)

    HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    prev_snap = HuntSnapshotService.generate_snapshot()

    await HuntDriftService.check_drift(mock_db, prev_snapshot=prev_snap)
    assert not mock_db.add.called


# --- 10. Snapshot rebuild consistency (3 tests) ---

def test_hunt_snapshot_generation():
    HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    snapshot = HuntSnapshotService.generate_snapshot()
    assert snapshot["summary"]["total_hunts"] == 1
    assert "coverage" in snapshot
    assert "hunts" in snapshot


def test_hunt_snapshot_consistency_cleared():
    HuntService.create_or_sync_hunt("Test Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)
    HuntSnapshotService.clear_snapshots()
    # get_snapshot should rebuild automatically
    snap = HuntSnapshotService.get_snapshot()
    assert snap["summary"]["total_hunts"] == 1


def test_hunt_snapshot_by_scope():
    scope_id = uuid.uuid4()
    HuntService.create_or_sync_hunt("Scoped Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH, scope_id=scope_id)
    HuntService.create_or_sync_hunt("Global Hunt", "Desc", HuntType.MANUAL, HuntSeverity.HIGH)

    snap_scoped = HuntSnapshotService.get_snapshot(scope_id)
    snap_global = HuntSnapshotService.get_snapshot(None)

    assert snap_scoped["summary"]["total_hunts"] == 1
    assert snap_global["summary"]["total_hunts"] == 2


# --- 11. AI Context Injection Tests (3 tests) ---

@pytest.mark.asyncio
async def test_ai_context_injection_asset():
    mock_db = AsyncMock()
    asset = Asset()
    asset.id = SCOPE_ID
    asset.scope_id = SCOPE_ID
    # Setup mock executive report and asset generation reports
    report = {
        "asset": {"id": str(SCOPE_ID), "scope_id": str(SCOPE_ID)},
        "risk": {},
        "findings": [],
        "exposure": {},
    }
    setup_test_db(mock_db, assets=[asset])

    from src.services.asset_report_service import AssetReportService
    from unittest.mock import patch

    # Seed a hunt
    HuntService.create_or_sync_hunt("Hunt 1", "...", HuntType.MANUAL, HuntSeverity.HIGH, scope_id=SCOPE_ID)

    with patch.object(AssetReportService, "generate_asset_report", AsyncMock(return_value=report)):
        ctx = await AIContextBuilder.build_asset_context(mock_db, SCOPE_ID)
        assert "threat_hunting_summary" in ctx
        assert "hunt_coverage" in ctx
        assert len(ctx["active_hunts"]) == 1


@pytest.mark.asyncio
async def test_ai_context_injection_executive():
    mock_db = AsyncMock()
    from src.services.executive_report_service import ExecutiveReportService
    from src.services.dashboard_trend_service import DashboardTrendService
    from unittest.mock import patch

    setup_test_db(mock_db)

    # Seed a hunt
    HuntService.create_or_sync_hunt("Hunt 1", "...", HuntType.MANUAL, HuntSeverity.HIGH)

    with patch.object(ExecutiveReportService, "get_executive_report", AsyncMock(return_value={})), \
         patch.object(DashboardTrendService, "generate_trends", AsyncMock(return_value=[])):
        ctx = await AIContextBuilder.build_executive_context(mock_db)
        assert "threat_hunting_summary" in ctx
        assert "hunt_coverage" in ctx


def test_ai_prompt_builder_restriction():
    context = {"threat_hunting_summary": {"total_hunts": 1}}
    prompt = AIPromptBuilder.build_asset_prompt(context)
    assert "creating, activating, modifying, assigning, completing, or closing threat hunts" in prompt


# --- 12. REST API Gateway Router Tests (10 tests) ---

@pytest.mark.asyncio
async def test_api_list_hunts(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    HuntService.create_or_sync_hunt("Hunt 1", "...", HuntType.MANUAL, HuntSeverity.HIGH, scope_id=SCOPE_ID)

    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/threat-hunting/hunts", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_api_get_hunt(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    h = HuntService.create_or_sync_hunt("Hunt 1", "...", HuntType.MANUAL, HuntSeverity.HIGH, scope_id=SCOPE_ID)

    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/threat-hunting/hunts/{h.hunt_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Hunt 1"


@pytest.mark.asyncio
async def test_api_get_hunt_metrics(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/threat-hunting/hunts/metrics?scope_id={SCOPE_ID}", headers=headers)
    assert resp.status_code == 200
    assert "summary" in resp.json()


@pytest.mark.asyncio
async def test_api_get_hunt_metrics_forbidden(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/threat-hunting/hunts/metrics", headers=headers)
    assert resp.status_code == 403  # Non-admin cannot request global metrics


@pytest.mark.asyncio
async def test_api_create_hunt(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {
        "title": "API Hunt",
        "description": "Created via API",
        "hunt_type": "MANUAL",
        "severity": "HIGH",
        "scope_id": str(SCOPE_ID),
    }
    resp = await client.post("/api/v1/threat-hunting/hunts", json=payload, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["title"] == "API Hunt"


@pytest.mark.asyncio
async def test_api_activate_hunt(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    h = HuntService.create_or_sync_hunt("Hunt 1", "...", HuntType.MANUAL, HuntSeverity.HIGH, scope_id=SCOPE_ID)

    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/threat-hunting/hunts/{h.hunt_id}/activate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_api_review_hunt(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    h = HuntService.create_or_sync_hunt("Hunt 1", "...", HuntType.MANUAL, HuntSeverity.HIGH, scope_id=SCOPE_ID)

    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/threat-hunting/hunts/{h.hunt_id}/review", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "UNDER_REVIEW"


@pytest.mark.asyncio
async def test_api_complete_hunt(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    h = HuntService.create_or_sync_hunt("Hunt 1", "...", HuntType.MANUAL, HuntSeverity.HIGH, scope_id=SCOPE_ID)

    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/threat-hunting/hunts/{h.hunt_id}/complete", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_api_close_hunt(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    h = HuntService.create_or_sync_hunt("Hunt 1", "...", HuntType.MANUAL, HuntSeverity.HIGH, scope_id=SCOPE_ID)

    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/threat-hunting/hunts/{h.hunt_id}/close", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_api_escalate_hunt(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    h = HuntService.create_or_sync_hunt("Hunt 1", "...", HuntType.MANUAL, HuntSeverity.HIGH, scope_id=SCOPE_ID)

    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/threat-hunting/hunts/{h.hunt_id}/escalate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ESCALATED"
