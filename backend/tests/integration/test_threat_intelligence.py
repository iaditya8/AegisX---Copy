import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.core.security import create_access_token
from src.domain.entities.threat_intelligence import (
    CampaignResponse,
    IOCResponse,
    IOCSeverity,
    IOCStatus,
    IOCType,
    ThreatActorResponse,
    ThreatFeedType,
)
from src.infrastructure.database.models import Asset, Finding, Scope, User
from src.services.campaign_registry import CampaignRegistry
from src.services.campaign_service import CampaignService
from src.services.ioc_correlation_service import IOCCorrelationRecord, IOCCorrelationService
from src.services.ioc_drift_service import IOCDriftService
from src.services.ioc_fingerprint_service import IOCFingerprintService
from src.services.ioc_history_service import IOCHistoryService
from src.services.ioc_service import IOCRecord, IOCService
from src.services.ioc_type_registry import IOCTypeRegistry
from src.services.threat_actor_registry import ThreatActorRegistry
from src.services.threat_actor_service import ThreatActorService
from src.services.threat_feed_registry import ThreatFeedRegistry
from src.services.threat_intelligence_snapshot_service import ThreatIntelligenceSnapshotService
from src.services.alert_lifecycle_service import AlertLifecycleService, AlertRecord
from src.services.incident_service import IncidentService, IncidentRecord
from src.services.case_service import CaseService, CaseRecord
from src.services.detection_service import DetectionService, DetectionRecord
from src.domain.entities.alert import AlertSeverity, AlertStatus, AlertType
from src.domain.entities.incident import IncidentSeverity, IncidentStatus
from src.domain.entities.case import CaseSeverity, CaseStatus
from src.domain.entities.detection import DetectionSeverity, DetectionStatus

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
    IOCService.clear_iocs()
    IOCHistoryService.clear_history()
    IOCCorrelationService.clear_correlations()
    ThreatIntelligenceSnapshotService.clear_snapshots()
    AlertLifecycleService.clear_alerts()
    IncidentService._incidents.clear()
    CaseService.clear_cases()
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
        return None

    mock_db.get = AsyncMock(side_effect=mock_get)

    async def mock_execute(query):
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


# --- 1. IOC Type Registry & Validation Tests (7 tests) ---


def test_ioc_type_validation_ip():
    """Verify registry validates IP addresses correctly."""
    assert IOCTypeRegistry.validate_value(IOCType.IP_ADDRESS, "192.168.1.1") is True
    assert IOCTypeRegistry.validate_value(IOCType.IP_ADDRESS, "999.999.999.999") is False


def test_ioc_type_validation_domain():
    """Verify registry validates domains correctly."""
    assert IOCTypeRegistry.validate_value(IOCType.DOMAIN, "google.com") is True
    assert IOCTypeRegistry.validate_value(IOCType.DOMAIN, "not-a-domain") is False


def test_ioc_type_validation_url():
    """Verify registry validates URLs correctly."""
    assert IOCTypeRegistry.validate_value(IOCType.URL, "https://example.com/path") is True
    assert IOCTypeRegistry.validate_value(IOCType.URL, "ftp://example.com") is False


def test_ioc_type_validation_email():
    """Verify registry validates emails correctly."""
    assert IOCTypeRegistry.validate_value(IOCType.EMAIL, "phish@threat.com") is True
    assert IOCTypeRegistry.validate_value(IOCType.EMAIL, "phish.threat.com") is False


def test_ioc_type_validation_md5():
    """Verify registry validates MD5 hashes correctly."""
    assert IOCTypeRegistry.validate_value(IOCType.MD5, "44d88612fe83b6b33b8a7f2277d3f431") is True
    assert IOCTypeRegistry.validate_value(IOCType.MD5, "44d88612fe83b6b33b8a7f2277d3f43") is False


def test_ioc_type_validation_sha1():
    """Verify registry validates SHA1 hashes correctly."""
    assert IOCTypeRegistry.validate_value(IOCType.SHA1, "a9993e364706816aba3e25717850c26c9cd0d89d") is True
    assert IOCTypeRegistry.validate_value(IOCType.SHA1, "a9993e364706816aba3e25717850c2") is False


def test_ioc_type_validation_sha256():
    """Verify registry validates SHA256 hashes correctly."""
    assert IOCTypeRegistry.validate_value(
        IOCType.SHA256, "248d6a61d20638b8e5f2571a3cf83db28c11a84f4f464010a300d8108cd3484f"
    ) is True
    assert IOCTypeRegistry.validate_value(IOCType.SHA256, "248d6a61d20638b8e") is False


# --- 2. IOC Normalization Tests (3 tests) ---


def test_ioc_normalization_domain():
    """Verify domains are lowercased and stripped."""
    assert IOCTypeRegistry.normalize_value(IOCType.DOMAIN, "  ThreatDomain.COM  ") == "threatdomain.com"


def test_ioc_normalization_email():
    """Verify emails are lowercased and stripped."""
    assert IOCTypeRegistry.normalize_value(IOCType.EMAIL, " Phish@Threat.COM ") == "phish@threat.com"


def test_ioc_normalization_hash():
    """Verify hashes are lowercased."""
    assert IOCTypeRegistry.normalize_value(IOCType.MD5, " 44D88612FE83B6B33B8A7F2277D3F431 ") == "44d88612fe83b6b33b8a7f2277d3f431"


# --- 3. Threat Feed Registry Tests (3 tests) ---


def test_threat_feed_registry_feeds():
    """Verify pre-seeded feeds exist."""
    assert ThreatFeedType.INTERNAL in ThreatFeedRegistry.get_registered_feeds()
    assert ThreatFeedType.COMMUNITY in ThreatFeedRegistry.get_registered_feeds()


def test_threat_feed_registry_validity():
    """Verify feed validity check."""
    assert ThreatFeedRegistry.is_valid_feed(ThreatFeedType.COMMERCIAL) is True
    assert ThreatFeedRegistry.is_valid_feed("INVALID_FEED") is False


def test_threat_feed_registry_all():
    """Verify we can retrieve all registered feeds."""
    assert len(ThreatFeedRegistry.get_registered_feeds()) == 3


# --- 4. Threat Actor Registry Tests (4 tests) ---


def test_threat_actor_registry_lazarus():
    """Verify Lazarus group pre-seeded profile."""
    actor = ThreatActorRegistry.get_actor_by_name("Lazarus")
    assert actor is not None
    assert actor.severity == IOCSeverity.CRITICAL
    assert "Hidden Cobra" in actor.aliases


def test_threat_actor_registry_apt29():
    """Verify APT29 pre-seeded profile."""
    actor = ThreatActorRegistry.get_actor_by_name("APT29")
    assert actor is not None
    assert actor.severity == IOCSeverity.CRITICAL


def test_threat_actor_registry_case_insensitive():
    """Verify actor lookup by case insensitive name or alias."""
    actor1 = ThreatActorRegistry.get_actor_by_name("lazarus")
    actor2 = ThreatActorRegistry.get_actor_by_name("fancy bear")
    assert actor1 is not None
    assert actor2 is not None
    assert actor2.name == "APT28"


def test_threat_actor_registry_all():
    """Verify getting all registered profiles."""
    profiles = ThreatActorRegistry.get_all_profiles()
    assert len(profiles) == 4


# --- 5. Campaign Registry Tests (3 tests) ---


def test_campaign_registry_ghost():
    """Verify Operation Ghost pre-seeded campaign details."""
    camp = CampaignRegistry.get_campaign_by_name("Operation Ghost")
    assert camp is not None
    assert camp.severity == IOCSeverity.CRITICAL
    assert "APT29" in camp.threat_actors


def test_campaign_registry_case_insensitive():
    """Verify campaign lookup is case insensitive."""
    camp = CampaignRegistry.get_campaign_by_name("operation ghost")
    assert camp is not None


def test_campaign_registry_all():
    """Verify getting all campaign profiles."""
    camps = CampaignRegistry.get_all_profiles()
    assert len(camps) == 2


# --- 6. IOC Fingerprint Service Tests (3 tests) ---


def test_ioc_fingerprint_sha256():
    """Verify SHA-256 generation."""
    fp = IOCFingerprintService.generate_fingerprint(IOCType.IP_ADDRESS, "1.1.1.1")
    assert len(fp) == 64


def test_ioc_fingerprint_stability():
    """Verify fingerprint is stable and deterministic."""
    fp1 = IOCFingerprintService.generate_fingerprint(IOCType.IP_ADDRESS, "8.8.8.8")
    fp2 = IOCFingerprintService.generate_fingerprint(IOCType.IP_ADDRESS, "8.8.8.8")
    assert fp1 == fp2


def test_ioc_fingerprint_normalization():
    """Verify fingerprinting normalizes the value first."""
    fp1 = IOCFingerprintService.generate_fingerprint(IOCType.DOMAIN, "ThreatDomain.COM")
    fp2 = IOCFingerprintService.generate_fingerprint(IOCType.DOMAIN, "threatdomain.com")
    assert fp1 == fp2


# --- 7. IOC History Service Tests (4 tests) ---


def test_ioc_history_logging():
    """Verify history logging adds entries."""
    ioc_id = uuid.uuid4()
    entry = IOCHistoryService.record_event(ioc_id, "CREATED", "Created active IOC")
    assert entry.event_type == "CREATED"
    assert len(IOCHistoryService.get_history(ioc_id)) == 1


def test_ioc_history_immutability():
    """Verify history entries cannot be modified or reordered."""
    ioc_id = uuid.uuid4()
    IOCHistoryService.record_event(ioc_id, "CREATED", "Created active IOC")
    IOCHistoryService.record_event(ioc_id, "UPDATED", "Updated metadata")
    history = IOCHistoryService.get_history(ioc_id)
    assert len(history) == 2
    assert history[0].event_type == "CREATED"
    assert history[1].event_type == "UPDATED"


def test_ioc_history_state_append():
    """Verify subsequent changes append to history."""
    ioc_id = uuid.uuid4()
    IOCHistoryService.record_event(ioc_id, "CREATED", "Created")
    IOCHistoryService.record_event(ioc_id, "EXPIRED", "Expired")
    history = IOCHistoryService.get_history(ioc_id)
    assert len(history) == 2


def test_ioc_history_clear():
    """Verify clearing history works."""
    ioc_id = uuid.uuid4()
    IOCHistoryService.record_event(ioc_id, "CREATED", "Created")
    IOCHistoryService.clear_history()
    assert len(IOCHistoryService.get_history(ioc_id)) == 0


# --- 8. IOC Service Lifecycle Tests (6 tests) ---


def test_ioc_service_create():
    """Verify IOC record creation."""
    ioc = IOCService.create_or_sync_ioc(
        value="1.1.1.1",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.CRITICAL,
        reputation=95,
        feed_type=ThreatFeedType.INTERNAL,
    )
    assert ioc.value == "1.1.1.1"
    assert ioc.status == IOCStatus.ACTIVE
    assert len(IOCService.get_all_iocs()) == 1


def test_ioc_service_sync_preserves_identity():
    """Verify synchronizing an existing IOC preserves its identity and timestamps."""
    ioc1 = IOCService.create_or_sync_ioc(
        value="threat.com",
        ioc_type=IOCType.DOMAIN,
        severity=IOCSeverity.MEDIUM,
        reputation=50,
        feed_type=ThreatFeedType.COMMUNITY,
    )
    created_at = ioc1.created_at

    # Sync again with updated severity/reputation
    ioc2 = IOCService.create_or_sync_ioc(
        value="threat.com",
        ioc_type=IOCType.DOMAIN,
        severity=IOCSeverity.HIGH,
        reputation=80,
        feed_type=ThreatFeedType.COMMUNITY,
    )
    assert ioc1.ioc_id == ioc2.ioc_id
    assert ioc2.severity == IOCSeverity.HIGH
    assert ioc2.reputation == 80
    assert ioc2.created_at == created_at


def test_ioc_service_expire():
    """Verify transitioning to EXPIRED status."""
    ioc = IOCService.create_or_sync_ioc(
        value="2.2.2.2",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.LOW,
        reputation=20,
        feed_type=ThreatFeedType.COMMUNITY,
    )
    expired = IOCService.expire_ioc(ioc.ioc_id)
    assert expired.status == IOCStatus.EXPIRED


def test_ioc_service_revoke():
    """Verify transitioning to REVOKED status."""
    ioc = IOCService.create_or_sync_ioc(
        value="3.3.3.3",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.LOW,
        reputation=10,
        feed_type=ThreatFeedType.COMMUNITY,
    )
    revoked = IOCService.revoke_ioc(ioc.ioc_id)
    assert revoked.status == IOCStatus.REVOKED


def test_ioc_service_terminal_expired():
    """Verify EXPIRED state is terminal and cannot be reactivated by sync."""
    ioc = IOCService.create_or_sync_ioc(
        value="phish@phishing.com",
        ioc_type=IOCType.EMAIL,
        severity=IOCSeverity.HIGH,
        reputation=90,
        feed_type=ThreatFeedType.INTERNAL,
    )
    IOCService.expire_ioc(ioc.ioc_id)
    assert ioc.status == IOCStatus.EXPIRED

    # Sync again, status should remain EXPIRED
    synced = IOCService.create_or_sync_ioc(
        value="phish@phishing.com",
        ioc_type=IOCType.EMAIL,
        severity=IOCSeverity.CRITICAL,
        reputation=99,
        feed_type=ThreatFeedType.INTERNAL,
    )
    assert synced.status == IOCStatus.EXPIRED


def test_ioc_service_terminal_revoked():
    """Verify REVOKED state is terminal and cannot be reactivated by sync."""
    ioc = IOCService.create_or_sync_ioc(
        value="44d88612fe83b6b33b8a7f2277d3f431",
        ioc_type=IOCType.MD5,
        severity=IOCSeverity.CRITICAL,
        reputation=100,
        feed_type=ThreatFeedType.INTERNAL,
    )
    IOCService.revoke_ioc(ioc.ioc_id)
    assert ioc.status == IOCStatus.REVOKED

    # Sync again, status should remain REVOKED
    synced = IOCService.create_or_sync_ioc(
        value="44d88612fe83b6b33b8a7f2277d3f431",
        ioc_type=IOCType.MD5,
        severity=IOCSeverity.HIGH,
        reputation=85,
        feed_type=ThreatFeedType.INTERNAL,
    )
    assert synced.status == IOCStatus.REVOKED


# --- 9. IOC Correlation Service Tests (6 tests) ---


@pytest.mark.asyncio
async def test_ioc_correlation_asset():
    """Verify correlating IOC against a mock Asset."""
    mock_db = AsyncMock()
    # Set up mock Asset
    asset = Asset()
    asset.id = uuid.uuid4()
    asset.ip = "192.168.1.100"
    asset.host = "badhost.com"
    asset.scope_id = SCOPE_ID
    asset.deleted_at = None

    setup_test_db(mock_db, assets=[asset])

    # Seed IOC
    ioc = IOCService.create_or_sync_ioc(
        value="192.168.1.100",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.CRITICAL,
        reputation=95,
        feed_type=ThreatFeedType.INTERNAL,
    )

    await IOCCorrelationService.correlate_iocs(mock_db)
    correlations = IOCCorrelationService.get_all_correlations()
    assert len(correlations) == 1
    assert correlations[0].entity_type == "Asset"
    assert correlations[0].entity_id == asset.id


@pytest.mark.asyncio
async def test_ioc_correlation_finding():
    """Verify correlating IOC against a mock Finding."""
    mock_db = AsyncMock()
    finding = Finding()
    finding.id = uuid.uuid4()
    finding.asset_id = uuid.uuid4()
    finding.title = "Suspicious traffic to phish@threat.com"
    finding.description = "Connection detected to phishing email server."
    finding.metadata_json = {}

    setup_test_db(mock_db, findings=[finding])

    ioc = IOCService.create_or_sync_ioc(
        value="phish@threat.com",
        ioc_type=IOCType.EMAIL,
        severity=IOCSeverity.HIGH,
        reputation=85,
        feed_type=ThreatFeedType.COMMUNITY,
    )

    await IOCCorrelationService.correlate_iocs(mock_db)
    correlations = IOCCorrelationService.get_all_correlations()
    assert len(correlations) == 1
    assert correlations[0].entity_type == "Finding"
    assert correlations[0].entity_id == finding.id


@pytest.mark.asyncio
async def test_ioc_correlation_alert():
    """Verify correlating IOC against a mock Alert."""
    mock_db = AsyncMock()
    setup_test_db(mock_db)

    # Mock Alert
    alert = AlertRecord(
        alert_id=uuid.uuid4(),
        alert_fingerprint="abc",
        alert_type=AlertType.ASSET_DRIFT,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        title="Alert referencing threatdomain.com",
        description="Inbound request from blocked domain.",
    )
    AlertLifecycleService._alerts[alert.alert_id] = alert

    ioc = IOCService.create_or_sync_ioc(
        value="threatdomain.com",
        ioc_type=IOCType.DOMAIN,
        severity=IOCSeverity.CRITICAL,
        reputation=90,
        feed_type=ThreatFeedType.COMMERCIAL,
    )

    await IOCCorrelationService.correlate_iocs(mock_db)
    correlations = IOCCorrelationService.get_all_correlations()
    assert len(correlations) == 1
    assert correlations[0].entity_type == "Alert"
    assert correlations[0].entity_id == alert.alert_id


@pytest.mark.asyncio
async def test_ioc_correlation_incident():
    """Verify correlating IOC against a mock Incident."""
    mock_db = AsyncMock()
    setup_test_db(mock_db)

    incident = IncidentRecord(
        incident_id=uuid.uuid4(),
        incident_fingerprint="xyz",
        title="Incident with compromised hash 44d88612fe83b6b33b8a7f2277d3f431",
        description="Compromised hash detected on endpoint.",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.TRIAGED,
    )
    IncidentService._incidents[incident.incident_id] = incident

    ioc = IOCService.create_or_sync_ioc(
        value="44d88612fe83b6b33b8a7f2277d3f431",
        ioc_type=IOCType.MD5,
        severity=IOCSeverity.CRITICAL,
        reputation=95,
        feed_type=ThreatFeedType.INTERNAL,
    )

    await IOCCorrelationService.correlate_iocs(mock_db)
    correlations = IOCCorrelationService.get_all_correlations()
    assert len(correlations) == 1
    assert correlations[0].entity_type == "Incident"
    assert correlations[0].entity_id == incident.incident_id


@pytest.mark.asyncio
async def test_ioc_correlation_case():
    """Verify correlating IOC against a mock Case."""
    mock_db = AsyncMock()
    setup_test_db(mock_db)

    case = CaseRecord(
        case_id=uuid.uuid4(),
        case_fingerprint="123",
        title="Case with malicious hash 248d6a61d20638b8e5f2571a3cf83db28c11a84f4f464010a300d8108cd3484f",
        description="Case targeting command control center.",
        severity=CaseSeverity.CRITICAL,
        status=CaseStatus.ACTIVE,
    )
    CaseService._cases[case.case_id] = case

    ioc = IOCService.create_or_sync_ioc(
        value="248d6a61d20638b8e5f2571a3cf83db28c11a84f4f464010a300d8108cd3484f",
        ioc_type=IOCType.SHA256,
        severity=IOCSeverity.CRITICAL,
        reputation=100,
        feed_type=ThreatFeedType.INTERNAL,
    )

    await IOCCorrelationService.correlate_iocs(mock_db)
    correlations = IOCCorrelationService.get_all_correlations()
    assert len(correlations) == 1
    assert correlations[0].entity_type == "Case"
    assert correlations[0].entity_id == case.case_id


@pytest.mark.asyncio
async def test_ioc_correlation_preservation():
    """Verify that running correlation again preserves existing correlation properties."""
    mock_db = AsyncMock()
    asset = Asset()
    asset.id = uuid.uuid4()
    asset.ip = "192.168.1.100"
    asset.host = "badhost.com"
    asset.scope_id = SCOPE_ID
    asset.deleted_at = None

    setup_test_db(mock_db, assets=[asset])

    ioc = IOCService.create_or_sync_ioc(
        value="192.168.1.100",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.CRITICAL,
        reputation=95,
        feed_type=ThreatFeedType.INTERNAL,
    )

    await IOCCorrelationService.correlate_iocs(mock_db)
    corr1 = IOCCorrelationService.get_all_correlations()[0]
    corr1_id = corr1.correlation_id
    corr1_created = corr1.created_at

    # Correlate again
    await IOCCorrelationService.correlate_iocs(mock_db)
    corr2 = IOCCorrelationService.get_all_correlations()[0]
    assert corr2.correlation_id == corr1_id
    assert corr2.created_at == corr1_created


# --- 10. IOC Posture Drift & Snapshot Service Tests (3 tests) ---


@pytest.mark.asyncio
async def test_ioc_drift_reputation():
    """Verify that reputation change triggers ioc.reputation_changed event."""
    mock_db = AsyncMock()
    mock_wf = MagicMock()
    mock_wf.id = uuid.uuid4()
    setup_test_db(mock_db, workflow=mock_wf)

    # Create IOC & Baseline snapshot
    ioc = IOCService.create_or_sync_ioc(
        value="192.168.1.200",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.MEDIUM,
        reputation=40,
        feed_type=ThreatFeedType.INTERNAL,
    )
    prev_snap = ThreatIntelligenceSnapshotService.generate_snapshot()

    # Update reputation
    IOCService.create_or_sync_ioc(
        value="192.168.1.200",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.MEDIUM,
        reputation=99,  # Changed reputation
        feed_type=ThreatFeedType.INTERNAL,
    )

    await IOCDriftService.check_drift(mock_db, prev_snapshot=prev_snap)
    assert mock_db.add.called
    event = mock_db.add.call_args[0][0]
    assert event.event_type == "ioc.reputation_changed"


@pytest.mark.asyncio
async def test_ioc_drift_attribution_severity():
    """Verify that attribution or severity change triggers ioc.drift event."""
    mock_db = AsyncMock()
    mock_wf = MagicMock()
    mock_wf.id = uuid.uuid4()
    setup_test_db(mock_db, workflow=mock_wf)

    # Create IOC & Baseline snapshot
    ioc = IOCService.create_or_sync_ioc(
        value="192.168.1.222",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.MEDIUM,
        reputation=50,
        feed_type=ThreatFeedType.INTERNAL,
        threat_actors=["FIN7"],
    )
    prev_snap = ThreatIntelligenceSnapshotService.generate_snapshot()

    # Update threat actors
    IOCService.create_or_sync_ioc(
        value="192.168.1.222",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.CRITICAL,  # Changed severity
        reputation=50,
        feed_type=ThreatFeedType.INTERNAL,
        threat_actors=["FIN7", "APT29"],  # Changed threat actors
    )

    await IOCDriftService.check_drift(mock_db, prev_snapshot=prev_snap)
    assert mock_db.add.called
    events = [call_arg[0][0].event_type for call_arg in mock_db.add.call_args_list]
    assert "ioc.drift" in events


def test_ti_snapshot_consistency():
    """Verify cache-only consistency dynamically rebuilds snapshot if missing."""
    IOCService.create_or_sync_ioc(
        value="192.168.1.5",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.CRITICAL,
        reputation=95,
        feed_type=ThreatFeedType.INTERNAL,
    )

    # Deleting cache
    ThreatIntelligenceSnapshotService.clear_snapshots()

    # Should rebuild dynamically
    snapshot = ThreatIntelligenceSnapshotService.get_snapshot()
    assert snapshot["summary"]["total_iocs"] == 1
    assert snapshot["summary"]["active_iocs"] == 1
    assert snapshot["summary"]["average_reputation"] == 95.0


# --- 11. REST API Gateway Router Tests (7 tests) ---


@pytest.mark.asyncio
async def test_api_list_iocs(client, mock_db, mock_scope):
    """Verify operators can retrieve their scoped IOC list via REST."""
    setup_basic_mock_db(mock_db, mock_scope)
    IOCService.create_or_sync_ioc(
        value="1.1.1.1",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.HIGH,
        reputation=80,
        feed_type=ThreatFeedType.INTERNAL,
        scope_id=SCOPE_ID,
    )

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.get("/api/v1/threat-intelligence/iocs", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["value"] == "1.1.1.1"


@pytest.mark.asyncio
async def test_api_get_ioc(client, mock_db, mock_scope):
    """Verify operators can fetch single scoped IOC detail."""
    setup_basic_mock_db(mock_db, mock_scope)
    ioc = IOCService.create_or_sync_ioc(
        value="threat.org",
        ioc_type=IOCType.DOMAIN,
        severity=IOCSeverity.CRITICAL,
        reputation=90,
        feed_type=ThreatFeedType.COMMERCIAL,
        scope_id=SCOPE_ID,
    )

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.get(f"/api/v1/threat-intelligence/iocs/{ioc.ioc_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["value"] == "threat.org"


@pytest.mark.asyncio
async def test_api_create_ioc(client, mock_db, mock_scope):
    """Verify operators can create an IOC under their owned scope."""
    setup_basic_mock_db(mock_db, mock_scope)

    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {
        "value": "phish@domain.com",
        "ioc_type": "EMAIL",
        "severity": "HIGH",
        "reputation": 75,
        "feed_type": "INTERNAL",
        "scope_id": str(SCOPE_ID),
        "threat_actors": ["Lazarus"],
        "campaigns": [],
    }
    response = await client.post("/api/v1/threat-intelligence/iocs", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["value"] == "phish@domain.com"
    assert "Lazarus" in data["threat_actors"]


@pytest.mark.asyncio
async def test_api_expire_ioc(client, mock_db, mock_scope):
    """Verify operators can expire scoped IOCs."""
    setup_basic_mock_db(mock_db, mock_scope)
    ioc = IOCService.create_or_sync_ioc(
        value="2.2.2.2",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.CRITICAL,
        reputation=90,
        feed_type=ThreatFeedType.INTERNAL,
        scope_id=SCOPE_ID,
    )

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.post(f"/api/v1/threat-intelligence/iocs/{ioc.ioc_id}/expire", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "EXPIRED"


@pytest.mark.asyncio
async def test_api_revoke_ioc(client, mock_db, mock_scope):
    """Verify operators can revoke scoped IOCs."""
    setup_basic_mock_db(mock_db, mock_scope)
    ioc = IOCService.create_or_sync_ioc(
        value="3.3.3.3",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.CRITICAL,
        reputation=90,
        feed_type=ThreatFeedType.INTERNAL,
        scope_id=SCOPE_ID,
    )

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.post(f"/api/v1/threat-intelligence/iocs/{ioc.ioc_id}/revoke", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "REVOKED"


@pytest.mark.asyncio
async def test_api_rbac_restrictions(client, mock_db, mock_scope):
    """Verify readers are blocked from executing mutations."""
    setup_basic_mock_db(mock_db, mock_scope)

    headers = get_auth_header(READER_ID, "reader")
    payload = {
        "value": "phish@domain.com",
        "ioc_type": "EMAIL",
        "severity": "HIGH",
        "reputation": 75,
        "feed_type": "INTERNAL",
        "scope_id": str(SCOPE_ID),
    }
    response = await client.post("/api/v1/threat-intelligence/iocs", json=payload, headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_api_scope_checks(client, mock_db, mock_scope, mock_scope_2):
    """Verify operators are blocked from mutating IOCs in scopes they do not own."""
    setup_basic_mock_db(mock_db, mock_scope, mock_scope_2)

    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {
        "value": "phish@domain.com",
        "ioc_type": "EMAIL",
        "severity": "HIGH",
        "reputation": 75,
        "feed_type": "INTERNAL",
        "scope_id": str(SCOPE_ID_2),  # Owned by someone else
    }
    response = await client.post("/api/v1/threat-intelligence/iocs", json=payload, headers=headers)
    assert response.status_code == 403
