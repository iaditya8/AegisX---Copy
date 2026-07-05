import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.security import create_access_token
from src.domain.entities.security_posture import (
    PostureSeverity,
    RiskStatus,
    RiskCategory,
    SecurityPostureResponse,
)
from src.infrastructure.database.models import Asset, Finding, Scope, User
from src.services.security_posture_registry import SecurityPostureRegistry
from src.services.risk_category_registry import RiskCategoryRegistry
from src.services.risk_severity_registry import RiskSeverityRegistry
from src.services.posture_fingerprint_service import PostureFingerprintService
from src.services.posture_history_service import PostureHistoryService
from src.services.risk_intelligence_service import RiskIntelligenceService
from src.services.risk_prioritization_service import RiskPrioritizationService
from src.services.risk_correlation_service import RiskCorrelationService
from src.services.security_posture_service import SecurityPostureService
from src.services.posture_drift_service import PostureDriftService
from src.services.security_posture_snapshot_service import SecurityPostureSnapshotService
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
    from src.services.exposure_service import ExposureService

    SecurityPostureService.clear_postures()
    PostureHistoryService.clear_history()
    RiskCorrelationService.clear_correlations()
    SecurityPostureSnapshotService.clear_snapshots()
    AlertLifecycleService.clear_alerts()
    IncidentService.clear_incidents()
    CaseService.clear_cases()
    HuntService.clear_hunts()
    PurpleTeamService.clear_exercises()
    PurpleTeamFindingService.clear_findings()
    ExposureService.clear_exposures()


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


def setup_test_db(mock_db, scopes=None, assets=None, findings=None):
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
            filtered_assets = assets or []
            try:
                params = query.compile().params
                q_scope_id = None
                for k, v in params.items():
                    if k.startswith("scope_id") or "scope" in k:
                        if isinstance(v, uuid.UUID) or (isinstance(v, str) and len(v) == 36):
                            q_scope_id = uuid.UUID(str(v))
                            break
                if q_scope_id:
                    filtered_assets = [a for a in filtered_assets if a.scope_id == q_scope_id]
            except Exception:
                pass
            mock_result.scalars().all.side_effect = lambda: filtered_assets
        elif "from findings" in query_str:
            mock_result.scalars().all.side_effect = lambda: findings or []
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


# --- 1. Registries Tests (8 tests) ---

def test_posture_registry_categories():
    categories = SecurityPostureRegistry.get_registered_categories()
    assert RiskCategory.ATTACK_SURFACE in categories
    assert RiskCategory.VULNERABILITY in categories


def test_posture_registry_valid_check():
    assert SecurityPostureRegistry.is_valid_category("VULNERABILITY") is True
    assert SecurityPostureRegistry.is_valid_category("invalid") is False


def test_posture_registry_resolve():
    res = SecurityPostureRegistry.resolve_category("COMPLIANCE")
    assert res == RiskCategory.COMPLIANCE


def test_posture_registry_resolve_fallback():
    res = SecurityPostureRegistry.resolve_category("invalid")
    assert res == RiskCategory.OPERATIONAL


def test_risk_category_supported():
    assert RiskCategoryRegistry.is_supported("IDENTITY") is True
    assert RiskCategoryRegistry.is_supported("invalid") is False


def test_risk_category_mappings():
    categories = RiskCategoryRegistry.get_supported_classifications()
    assert "ATTACK_SURFACE" in categories


def test_severity_resolve():
    assert RiskSeverityRegistry.resolve_severity("CRITICAL") == PostureSeverity.CRITICAL
    assert RiskSeverityRegistry.resolve_severity("invalid") == PostureSeverity.LOW


def test_severity_highest():
    highest = RiskSeverityRegistry.get_highest_severity(["LOW", "HIGH", "MEDIUM"])
    assert highest == PostureSeverity.HIGH


# --- 2. Fingerprinting Tests (4 tests) ---

def test_fingerprint_stability():
    fp1 = PostureFingerprintService.generate_fingerprint(RiskCategory.VULNERABILITY, ASSET_ID, "src")
    fp2 = PostureFingerprintService.generate_fingerprint(RiskCategory.VULNERABILITY, ASSET_ID, "src")
    assert fp1 == fp2


def test_fingerprint_normalization():
    fp1 = PostureFingerprintService.generate_fingerprint(RiskCategory.VULNERABILITY, ASSET_ID, "  src  ")
    fp2 = PostureFingerprintService.generate_fingerprint(RiskCategory.VULNERABILITY, ASSET_ID, "SRC")
    assert fp1 == fp2


def test_fingerprint_casing():
    fp1 = PostureFingerprintService.generate_fingerprint(RiskCategory.VULNERABILITY, ASSET_ID, "src")
    fp2 = PostureFingerprintService.generate_fingerprint(RiskCategory.VULNERABILITY, ASSET_ID, "SRC")
    assert fp1 == fp2


def test_fingerprint_length():
    fp = PostureFingerprintService.generate_fingerprint(RiskCategory.VULNERABILITY, ASSET_ID, "src")
    assert len(fp) == 64


# --- 3. History Preservation Tests (5 tests) ---

@pytest.mark.asyncio
async def test_posture_history_empty(mock_db):
    assert len(await PostureHistoryService.get_history(uuid.uuid4())) == 0


@pytest.mark.asyncio
async def test_posture_history_record(mock_db):
    pid = uuid.uuid4()
    entry = await PostureHistoryService.record_event(pid, "CREATED", "Created")
    assert entry.posture_id == pid
    assert entry.event_type == "CREATED"


@pytest.mark.asyncio
async def test_posture_history_preserved(mock_db):
    pid = uuid.uuid4()
    await PostureHistoryService.record_event(pid, "CREATED", "Created")
    history = await PostureHistoryService.get_history(pid)
    assert len(history) == 1
    assert history[0].event_type == "CREATED"


@pytest.mark.asyncio
async def test_posture_history_deepcopied(mock_db):
    pid = uuid.uuid4()
    entry = await PostureHistoryService.record_event(pid, "CREATED", "Created")
    history1 = await PostureHistoryService.get_history(pid)
    history2 = await PostureHistoryService.get_history(pid)
    assert history1 is not history2
    assert history1[0] == history2[0]


@pytest.mark.asyncio
async def test_posture_history_clear(mock_db):
    from src.infrastructure.database.models import SecurityPostureHistory
    pid = uuid.uuid4()
    await PostureHistoryService.record_event(pid, "CREATED", "Created")
    PostureHistoryService.clear_history()
    mock_db._entities[SecurityPostureHistory] = []
    assert len(await PostureHistoryService.get_history(pid)) == 0


# --- 4. Risk Scoring & Prioritization Tests (6 tests) ---

def test_risk_score_calculation():
    res = RiskIntelligenceService.calculate_risk(ASSET_ID, RiskCategory.VULNERABILITY, PostureSeverity.CRITICAL)
    assert res["likelihood"] == 0.95
    assert res["impact"] == 0.90
    assert res["risk_score"] == 85.50
    assert res["posture_score"] == 14.50


def test_risk_score_stability():
    res1 = RiskIntelligenceService.calculate_risk(ASSET_ID, RiskCategory.VULNERABILITY, PostureSeverity.HIGH)
    res2 = RiskIntelligenceService.calculate_risk(ASSET_ID, RiskCategory.VULNERABILITY, PostureSeverity.HIGH)
    assert res1["risk_score"] == res2["risk_score"]


def test_risk_prioritization():
    postures = [
        MagicMock(severity=PostureSeverity.LOW, risk_score=10.0),
        MagicMock(severity=PostureSeverity.CRITICAL, risk_score=80.0),
        MagicMock(severity=PostureSeverity.HIGH, risk_score=60.0),
    ]
    sorted_posts = RiskPrioritizationService.prioritize_postures(postures)
    assert sorted_posts[0].severity == PostureSeverity.CRITICAL
    assert sorted_posts[2].severity == PostureSeverity.LOW


def test_risk_prioritization_same_severity():
    postures = [
        MagicMock(severity=PostureSeverity.HIGH, risk_score=50.0),
        MagicMock(severity=PostureSeverity.HIGH, risk_score=70.0),
    ]
    sorted_posts = RiskPrioritizationService.prioritize_postures(postures)
    assert sorted_posts[0].risk_score == 70.0


def test_risk_prioritization_empty():
    assert len(RiskPrioritizationService.prioritize_postures([])) == 0


def test_risk_prioritization_stable_sort():
    postures = [
        MagicMock(severity=PostureSeverity.LOW, risk_score=20.0),
        MagicMock(severity=PostureSeverity.LOW, risk_score=20.0),
    ]
    sorted_posts = RiskPrioritizationService.prioritize_postures(postures)
    assert len(sorted_posts) == 2


# --- 5. Correlations Tests (10 tests) ---

@pytest.mark.asyncio
async def test_risk_correlation_empty(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.detection_service import DetectionService
    from src.services.threat_actor_service import ThreatActorService
    from src.services.campaign_service import CampaignService

    with patch.object(DetectionService, "get_all_detections", return_value=[]), \
         patch.object(ThreatActorService, "get_all_actors", return_value=[]), \
         patch.object(CampaignService, "get_all_campaigns", return_value=[]):
        res = await RiskCorrelationService.correlate_posture(mock_db, uuid.uuid4(), ASSET_ID)
        assert len(res) == 0


@pytest.mark.asyncio
async def test_risk_correlation_findings(mock_db):
    finding = Finding()
    finding.id = uuid.uuid4()
    finding.asset_id = ASSET_ID
    finding.title = "Vulnerable framework"
    setup_test_db(mock_db, findings=[finding])
    from src.services.detection_service import DetectionService
    from src.services.threat_actor_service import ThreatActorService
    from src.services.campaign_service import CampaignService

    with patch.object(DetectionService, "get_all_detections", return_value=[]), \
         patch.object(ThreatActorService, "get_all_actors", return_value=[]), \
         patch.object(CampaignService, "get_all_campaigns", return_value=[]):
        res = await RiskCorrelationService.correlate_posture(mock_db, uuid.uuid4(), ASSET_ID)
        assert any(r["entity_type"] == "Finding" and r["entity_id"] == str(finding.id) for r in res)


@pytest.mark.asyncio
async def test_risk_correlation_exposures(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.exposure_service import ExposureService
    from src.services.detection_service import DetectionService
    from src.services.threat_actor_service import ThreatActorService
    from src.services.campaign_service import CampaignService

    exposure = MagicMock(exposure_id=uuid.uuid4(), asset_id=ASSET_ID, title="Exposure 1")
    
    with patch.object(ExposureService, "get_all_exposures", return_value=[exposure]), \
         patch.object(DetectionService, "get_all_detections", return_value=[]), \
         patch.object(ThreatActorService, "get_all_actors", return_value=[]), \
         patch.object(CampaignService, "get_all_campaigns", return_value=[]):
        res = await RiskCorrelationService.correlate_posture(mock_db, uuid.uuid4(), ASSET_ID)
        assert any(r["entity_type"] == "Exposure" and r["entity_id"] == str(exposure.exposure_id) for r in res)


@pytest.mark.asyncio
async def test_risk_correlation_incidents(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.incident_service import IncidentService
    from src.services.detection_service import DetectionService
    from src.services.threat_actor_service import ThreatActorService
    from src.services.campaign_service import CampaignService

    incident = MagicMock(incident_id=uuid.uuid4(), asset_ids=[ASSET_ID], title="Incident 1")
    
    with patch.object(IncidentService, "get_all_incidents", return_value=[incident]), \
         patch.object(DetectionService, "get_all_detections", return_value=[]), \
         patch.object(ThreatActorService, "get_all_actors", return_value=[]), \
         patch.object(CampaignService, "get_all_campaigns", return_value=[]):
        res = await RiskCorrelationService.correlate_posture(mock_db, uuid.uuid4(), ASSET_ID)
        assert any(r["entity_type"] == "Incident" and r["entity_id"] == str(incident.incident_id) for r in res)


@pytest.mark.asyncio
async def test_risk_correlation_cases(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.case_service import CaseService
    from src.services.detection_service import DetectionService
    from src.services.threat_actor_service import ThreatActorService
    from src.services.campaign_service import CampaignService

    case = MagicMock(case_id=uuid.uuid4(), asset_ids=[ASSET_ID], title="Case 1")
    
    with patch.object(CaseService, "get_all_cases", return_value=[case]), \
         patch.object(DetectionService, "get_all_detections", return_value=[]), \
         patch.object(ThreatActorService, "get_all_actors", return_value=[]), \
         patch.object(CampaignService, "get_all_campaigns", return_value=[]):
        res = await RiskCorrelationService.correlate_posture(mock_db, uuid.uuid4(), ASSET_ID)
        assert any(r["entity_type"] == "Case" and r["entity_id"] == str(case.case_id) for r in res)


@pytest.mark.asyncio
async def test_risk_correlation_hunts(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.hunt_service import HuntService
    from src.services.detection_service import DetectionService
    from src.services.threat_actor_service import ThreatActorService
    from src.services.campaign_service import CampaignService

    hunt = MagicMock(
        hunt_id=uuid.uuid4(),
        related_entities=[{"entity_id": str(ASSET_ID)}],
        title="Hunt 1"
    )
    
    with patch.object(HuntService, "get_all_hunts", return_value=[hunt]), \
         patch.object(DetectionService, "get_all_detections", return_value=[]), \
         patch.object(ThreatActorService, "get_all_actors", return_value=[]), \
         patch.object(CampaignService, "get_all_campaigns", return_value=[]):
        res = await RiskCorrelationService.correlate_posture(mock_db, uuid.uuid4(), ASSET_ID)
        assert any(r["entity_type"] == "Hunt" and r["entity_id"] == str(hunt.hunt_id) for r in res)


@pytest.mark.asyncio
async def test_risk_correlation_detections(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.detection_service import DetectionService
    from src.services.threat_actor_service import ThreatActorService
    from src.services.campaign_service import CampaignService

    detection = MagicMock(detection_id=uuid.uuid4(), name="Rule 1")
    
    with patch.object(DetectionService, "get_all_detections", return_value=[detection]), \
         patch.object(ThreatActorService, "get_all_actors", return_value=[]), \
         patch.object(CampaignService, "get_all_campaigns", return_value=[]):
        res = await RiskCorrelationService.correlate_posture(mock_db, uuid.uuid4(), ASSET_ID)
        assert any(r["entity_type"] == "Detection" and r["entity_id"] == str(detection.detection_id) for r in res)


@pytest.mark.asyncio
async def test_risk_correlation_campaigns(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.campaign_service import CampaignService
    from src.services.detection_service import DetectionService
    from src.services.threat_actor_service import ThreatActorService

    campaign = MagicMock(campaign_id=uuid.uuid4(), name="Campaign 1")
    
    with patch.object(CampaignService, "get_all_campaigns", return_value=[campaign]), \
         patch.object(DetectionService, "get_all_detections", return_value=[]), \
         patch.object(ThreatActorService, "get_all_actors", return_value=[]):
        res = await RiskCorrelationService.correlate_posture(mock_db, uuid.uuid4(), ASSET_ID)
        assert any(r["entity_type"] == "Campaign" and r["entity_id"] == str(campaign.campaign_id) for r in res)


@pytest.mark.asyncio
async def test_risk_correlation_actors(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.threat_actor_service import ThreatActorService
    from src.services.detection_service import DetectionService
    from src.services.campaign_service import CampaignService

    actor = MagicMock(actor_id=uuid.uuid4(), name="Actor 1")
    
    with patch.object(ThreatActorService, "get_all_actors", return_value=[actor]), \
         patch.object(DetectionService, "get_all_detections", return_value=[]), \
         patch.object(CampaignService, "get_all_campaigns", return_value=[]):
        res = await RiskCorrelationService.correlate_posture(mock_db, uuid.uuid4(), ASSET_ID)
        assert any(r["entity_type"] == "ThreatActor" and r["entity_id"] == str(actor.actor_id) for r in res)


@pytest.mark.asyncio
async def test_risk_correlation_preservation(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    from src.services.threat_actor_service import ThreatActorService
    from src.services.detection_service import DetectionService
    from src.services.campaign_service import CampaignService

    actor = MagicMock(actor_id=uuid.uuid4(), name="Actor 1")
    
    with patch.object(ThreatActorService, "get_all_actors", return_value=[actor]), \
         patch.object(DetectionService, "get_all_detections", return_value=[]), \
         patch.object(CampaignService, "get_all_campaigns", return_value=[]):
        pid = uuid.uuid4()
        await RiskCorrelationService.correlate_posture(mock_db, pid, ASSET_ID)
        # Verify second call appends and does not override
        res = await RiskCorrelationService.correlate_posture(mock_db, pid, ASSET_ID)
        assert any(r["entity_type"] == "ThreatActor" and r["entity_id"] == str(actor.actor_id) for r in res)
        # Clear/Close should not delete historical correlations
        assert len(RiskCorrelationService.get_correlations(pid)) == 1


# --- 6. Posture Service & State Machine Lifecycle (12 tests) ---

@pytest.mark.asyncio
async def test_posture_auto_creation(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    p = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    assert p.status == RiskStatus.OPEN
    assert p.risk_score > 0.0


@pytest.mark.asyncio
async def test_posture_fingerprint_stability(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    p1 = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    p2 = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc 2", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    assert p1.posture_id == p2.posture_id


@pytest.mark.asyncio
async def test_posture_sync_preserves_identity(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    p1 = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    p2 = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc 2", RiskCategory.VULNERABILITY, PostureSeverity.MEDIUM, ASSET_ID, "src"
    )
    assert p1.posture_id == p2.posture_id
    assert p2.severity == PostureSeverity.MEDIUM


@pytest.mark.asyncio
async def test_posture_duplicate_prevention(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    assert len(SecurityPostureService.get_all_postures()) == 1


@pytest.mark.asyncio
async def test_posture_accept_transition(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    p = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    updated = await SecurityPostureService.accept_risk(p.posture_id)
    assert updated.status == RiskStatus.ACCEPTED


@pytest.mark.asyncio
async def test_posture_mitigate_transition(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    p = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    updated = await SecurityPostureService.mitigate_risk(p.posture_id)
    assert updated.status == RiskStatus.MITIGATED


@pytest.mark.asyncio
async def test_posture_close_transition(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    p = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    updated = await SecurityPostureService.close_posture(p.posture_id)
    assert updated.status == RiskStatus.CLOSED


@pytest.mark.asyncio
async def test_posture_identity_preserved_after_acceptance(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    p = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    await SecurityPostureService.accept_risk(p.posture_id)
    p2 = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    assert p2.posture_id == p.posture_id
    assert p2.status == RiskStatus.ACCEPTED


@pytest.mark.asyncio
async def test_posture_identity_preserved_after_mitigation(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    p = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    await SecurityPostureService.mitigate_risk(p.posture_id)
    p2 = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    assert p2.posture_id == p.posture_id
    assert p2.status == RiskStatus.MITIGATED


@pytest.mark.asyncio
async def test_posture_identity_preserved_after_closure(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    p = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    await SecurityPostureService.close_posture(p.posture_id)
    p2 = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    assert p2.posture_id == p.posture_id
    assert p2.status == RiskStatus.CLOSED


@pytest.mark.asyncio
async def test_posture_terminal_state_enforcement(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    p = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    await SecurityPostureService.close_posture(p.posture_id)
    with pytest.raises(ValueError):
        await SecurityPostureService.accept_risk(p.posture_id)


@pytest.mark.asyncio
async def test_posture_terminal_state_not_reactivated_by_sync(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    p = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    await SecurityPostureService.close_posture(p.posture_id)
    
    # Run sync to verify CLOSED is preserved
    p2 = await SecurityPostureService.create_or_sync_posture(
        "Posture Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.CRITICAL, ASSET_ID, "src"
    )
    assert p2.status == RiskStatus.CLOSED


# --- 7. Drift Detection Tests (8 tests) ---

@pytest.mark.asyncio
async def test_posture_drift_detection(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    prev = {
        "summary": {
            "organizational_risk_score": 10.0,
            "security_posture_score": 90.0,
            "critical_risk_count": 0,
            "attack_surface_coverage": 100.0,
        }
    }
    
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await SecurityPostureService.create_or_sync_posture(
            "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.CRITICAL, ASSET_ID, "src"
        )
        await PostureDriftService.check_drift(mock_db, SCOPE_ID, prev)
        assert mock_emit.call_count >= 1


@pytest.mark.asyncio
async def test_risk_increase_detection(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    prev = {
        "summary": {
            "organizational_risk_score": 5.0,
            "security_posture_score": 95.0,
            "critical_risk_count": 0,
            "attack_surface_coverage": 100.0,
        }
    }
    
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await SecurityPostureService.create_or_sync_posture(
            "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.CRITICAL, ASSET_ID, "src"
        )
        await PostureDriftService.check_drift(mock_db, SCOPE_ID, prev)
        events = [c.kwargs["payload"]["drift_type"] for c in mock_emit.call_args_list]
        assert "RISK_INCREASED" in events


@pytest.mark.asyncio
async def test_risk_decrease_detection(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    prev = {
        "summary": {
            "organizational_risk_score": 95.0,
            "security_posture_score": 5.0,
            "critical_risk_count": 1,
            "attack_surface_coverage": 100.0,
        }
    }
    
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await PostureDriftService.check_drift(mock_db, SCOPE_ID, prev)
        events = [c.kwargs["payload"]["drift_type"] for c in mock_emit.call_args_list]
        assert "RISK_DECREASED" in events


@pytest.mark.asyncio
async def test_posture_changed_drift(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    prev = {
        "summary": {
            "organizational_risk_score": 10.0,
            "security_posture_score": 50.0,
            "critical_risk_count": 0,
            "attack_surface_coverage": 100.0,
        }
    }
    
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await PostureDriftService.check_drift(mock_db, SCOPE_ID, prev)
        events = [c.kwargs["payload"]["drift_type"] for c in mock_emit.call_args_list]
        assert "POSTURE_CHANGED" in events


@pytest.mark.asyncio
async def test_exposure_increased_drift(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    prev = {
        "summary": {
            "organizational_risk_score": 10.0,
            "security_posture_score": 90.0,
            "critical_risk_count": 0,
            "attack_surface_coverage": 100.0,
        }
    }
    
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await SecurityPostureService.create_or_sync_posture(
            "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.CRITICAL, ASSET_ID, "src"
        )
        await PostureDriftService.check_drift(mock_db, SCOPE_ID, prev)
        events = [c.kwargs["payload"]["drift_type"] for c in mock_emit.call_args_list]
        assert "EXPOSURE_INCREASED" in events


@pytest.mark.asyncio
async def test_exposure_decreased_drift(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    prev = {
        "summary": {
            "organizational_risk_score": 10.0,
            "security_posture_score": 90.0,
            "critical_risk_count": 5,
            "attack_surface_coverage": 100.0,
        }
    }
    
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await PostureDriftService.check_drift(mock_db, SCOPE_ID, prev)
        events = [c.kwargs["payload"]["drift_type"] for c in mock_emit.call_args_list]
        assert "EXPOSURE_DECREASED" in events


@pytest.mark.asyncio
async def test_coverage_changed_drift(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    prev = {
        "summary": {
            "organizational_risk_score": 0.0,
            "security_posture_score": 100.0,
            "critical_risk_count": 0,
            "attack_surface_coverage": 50.0,
        }
    }
    
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await PostureDriftService.check_drift(mock_db, SCOPE_ID, prev)
        events = [c.kwargs["payload"]["drift_type"] for c in mock_emit.call_args_list]
        assert "COVERAGE_CHANGED" in events


@pytest.mark.asyncio
async def test_drift_empty_prev(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await PostureDriftService.check_drift(mock_db, SCOPE_ID, None)
        assert mock_emit.call_count == 0


# --- 8. Snapshot & Rebuild Tests (6 tests) ---

@pytest.mark.asyncio
async def test_snapshot_rebuild_consistency(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityPostureService.create_or_sync_posture(
        "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    snap = await SecurityPostureSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    assert snap["summary"]["total_postures"] == 1


@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_deletion(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityPostureService.create_or_sync_posture(
        "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    await SecurityPostureSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    SecurityPostureSnapshotService.clear_snapshots()
    snap = SecurityPostureSnapshotService.get_snapshot(SCOPE_ID)
    assert snap["summary"]["total_postures"] == 0


@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_corruption(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    SecurityPostureSnapshotService._snapshots[SCOPE_ID] = {"corrupted": True}
    snap = await SecurityPostureSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    assert "summary" in snap
    assert "corrupted" not in snap


@pytest.mark.asyncio
async def test_executive_risk_metrics_rebuild(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityPostureService.create_or_sync_posture(
        "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.CRITICAL, ASSET_ID, "src"
    )
    await SecurityPostureSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    snap = SecurityPostureSnapshotService.get_snapshot(SCOPE_ID)
    assert snap["summary"]["critical_risk_count"] == 1


@pytest.mark.asyncio
async def test_snapshot_trends_limit(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    for _ in range(15):
        await SecurityPostureSnapshotService.generate_snapshot(mock_db, SCOPE_ID)
    snap = SecurityPostureSnapshotService.get_snapshot(SCOPE_ID)
    assert len(snap["summary"]["risk_trends"]) <= 10


@pytest.mark.asyncio
async def test_snapshot_filter_by_scope(mock_db, mock_scope, mock_scope_2):
    setup_basic_mock_db(mock_db, mock_scope, mock_scope_2)
    asset2 = Asset()
    asset2.id = uuid.uuid4()
    asset2.scope_id = mock_scope_2.id
    setup_test_db(mock_db, scopes=[mock_scope, mock_scope_2], assets=[asset2])

    await SecurityPostureService.create_or_sync_posture(
        "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, asset2.id, "src"
    )
    snap1 = await SecurityPostureSnapshotService.generate_snapshot(mock_db, mock_scope.id)
    snap2 = await SecurityPostureSnapshotService.generate_snapshot(mock_db, mock_scope_2.id)
    assert snap1["summary"]["total_postures"] == 0
    assert snap2["summary"]["total_postures"] == 1


# --- 9. AI Context & Safe Guards Tests (4 tests) ---

@pytest.mark.asyncio
async def test_ai_context_posture_injection(mock_db):
    setup_basic_mock_db(mock_db, Scope())
    await SecurityPostureService.create_or_sync_posture(
        "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    await SecurityPostureSnapshotService.generate_snapshot(mock_db, SCOPE_ID)

    from src.services.asset_report_service import AssetReportService
    mock_report = {
        "asset": {"id": str(ASSET_ID), "scope_id": SCOPE_ID},
        "risk": {},
        "findings": [],
        "exposure": {}
    }

    with patch.object(AssetReportService, "generate_asset_report", new_callable=AsyncMock, return_value=mock_report):
        ctx = await AIContextBuilder.build_asset_context(mock_db, ASSET_ID)
        assert "security_posture_summary" in ctx["asset"]
        assert "active_postures" in ctx["asset"]


def test_ai_advisory_only_enforcement():
    context = {"dummy": "data"}
    prompt = AIPromptBuilder.build_asset_prompt(context)
    assert "security posture" in prompt
    assert "validating, accepting, mitigating, closing" in prompt


def test_ai_finding_prompt_constraints():
    context = {"dummy": "data"}
    prompt = AIPromptBuilder.build_finding_prompt(context)
    assert "security postures" in prompt


def test_ai_executive_prompt_constraints():
    context = {"dummy": "data"}
    prompt = AIPromptBuilder.build_executive_prompt(context)
    assert "security postures" in prompt


# --- 10. API Gateway Router Tests (15 tests) ---

@pytest.mark.asyncio
async def test_api_list_postures(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityPostureService.create_or_sync_posture(
        "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-posture", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_api_list_open_postures(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityPostureService.create_or_sync_posture(
        "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-posture/open", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_api_list_critical_postures(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityPostureService.create_or_sync_posture(
        "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.CRITICAL, ASSET_ID, "src"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-posture/critical", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_api_get_posture(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityPostureService.create_or_sync_posture(
        "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/security-posture/{p.posture_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "Title"


@pytest.mark.asyncio
async def test_api_create_posture(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {
        "title": "API Post",
        "description": "Desc via API",
        "category": "VULNERABILITY",
        "severity": "HIGH",
        "asset_id": str(ASSET_ID),
        "risk_source": "src",
    }
    resp = await client.post("/api/v1/security-posture", json=payload, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["data"]["title"] == "API Post"


@pytest.mark.asyncio
async def test_api_accept_posture(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityPostureService.create_or_sync_posture(
        "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-posture/{p.posture_id}/accept", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_api_mitigate_posture(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityPostureService.create_or_sync_posture(
        "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-posture/{p.posture_id}/mitigate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "MITIGATED"


@pytest.mark.asyncio
async def test_api_close_posture(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityPostureService.create_or_sync_posture(
        "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-posture/{p.posture_id}/close", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_api_rbac_permissions(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    p = await SecurityPostureService.create_or_sync_posture(
        "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, ASSET_ID, "src"
    )
    headers = get_auth_header(READER_ID, "reader")
    resp = await client.post(f"/api/v1/security-posture/{p.posture_id}/accept", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_rbac_reader_restrictions(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(READER_ID, "reader")
    payload = {
        "title": "API Post",
        "description": "Desc via API",
        "category": "VULNERABILITY",
        "severity": "HIGH",
        "asset_id": str(ASSET_ID),
        "risk_source": "src",
    }
    resp = await client.post("/api/v1/security-posture", json=payload, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_rbac_scope_validation(client, mock_db, mock_scope, mock_scope_2):
    setup_basic_mock_db(mock_db, mock_scope, mock_scope_2)
    asset_other = Asset()
    asset_other.id = uuid.uuid4()
    asset_other.scope_id = mock_scope_2.id
    asset_other.deleted_at = None
    setup_test_db(mock_db, scopes=[mock_scope, mock_scope_2], assets=[asset_other])

    p = await SecurityPostureService.create_or_sync_posture(
        "Title", "Desc", RiskCategory.VULNERABILITY, PostureSeverity.HIGH, asset_other.id, "src"
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/security-posture/{p.posture_id}", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_drift_check(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-posture/drift", headers=headers)
    assert resp.status_code == 200
    assert "snapshot" in resp.json()["data"]


@pytest.mark.asyncio
async def test_api_summary(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-posture/summary", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_not_found(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/security-posture/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_invalid_payload(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post("/api/v1/security-posture", json={}, headers=headers)
    assert resp.status_code == 400
