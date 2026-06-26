import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.core.security import create_access_token
from src.domain.entities.alert import AlertSeverity, AlertStatus, AlertType
from src.domain.entities.incident import IncidentSeverity, IncidentStatus
from src.infrastructure.database.models import Asset, Finding, Scope, User
from src.services.ai_context_builder import AIContextBuilder
from src.services.alert_lifecycle_service import AlertLifecycleService, AlertRecord
from src.services.incident_escalation_service import IncidentEscalationService
from src.services.incident_evidence_service import IncidentEvidenceService
from src.services.incident_fingerprint_service import IncidentFingerprintService
from src.services.incident_history_service import IncidentHistoryService
from src.services.incident_service import IncidentRecord, IncidentService
from src.services.incident_severity_registry import IncidentSeverityRegistry
from src.services.incident_snapshot_service import IncidentSnapshotService
from src.services.investigation_service import InvestigationService

ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OPERATOR_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
SCOPE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
ASSET_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
FINDING_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


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
def mock_scope() -> Scope:
    s = Scope()
    s.id = SCOPE_ID
    s.owner_id = OPERATOR_ID
    s.name = "Test Scope"
    s.type = "domain"
    s.deleted_at = None
    return s


@pytest.fixture
def mock_asset() -> Asset:
    a = Asset()
    a.id = ASSET_ID
    a.scope_id = SCOPE_ID
    a.host = "test.com"
    a.ip = "192.168.1.100"
    a.asset_type = "host"
    a.metadata_json = {}
    a.first_seen = datetime.now(timezone.utc)
    a.last_seen = datetime.now(timezone.utc)
    a.fingerprint = "test-fp"
    a.deleted_at = None
    return a


@pytest.fixture
def mock_finding() -> Finding:
    f = Finding()
    f.id = FINDING_ID
    f.asset_id = ASSET_ID
    f.title = "Critical Vuln"
    f.severity = "critical"
    f.status = "open"
    f.first_seen = datetime.now(timezone.utc)
    f.last_seen = datetime.now(timezone.utc)
    return f


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


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


@pytest.fixture(autouse=True)
def clean_stores():
    IncidentService.clear_incidents()
    IncidentHistoryService.clear_history()
    IncidentEvidenceService.clear_evidence()
    IncidentSnapshotService.clear_snapshots()
    InvestigationService.clear_investigations()
    AlertLifecycleService.clear_alerts()


def setup_basic_mock_db(mock_db, mock_asset, mock_finding):
    mock_db.get = AsyncMock(
        side_effect=lambda model, ident: (
            mock_asset
            if model == Asset
            else (mock_finding if model == Finding else None)
        )
    )


# --- Unit & Integration Tests ---


def test_incident_severity_registry() -> None:
    """Verify registry map severity logic correctly."""
    assert (
        IncidentSeverityRegistry.calculate_severity([AlertSeverity.CRITICAL])
        == IncidentSeverity.CRITICAL
    )
    assert (
        IncidentSeverityRegistry.calculate_severity(
            [AlertSeverity.HIGH, AlertSeverity.HIGH]
        )
        == IncidentSeverity.HIGH
    )
    assert (
        IncidentSeverityRegistry.calculate_severity(
            [AlertSeverity.MEDIUM, AlertSeverity.MEDIUM]
        )
        == IncidentSeverity.MEDIUM
    )
    assert (
        IncidentSeverityRegistry.calculate_severity(
            [AlertSeverity.LOW, AlertSeverity.LOW, AlertSeverity.LOW]
        )
        == IncidentSeverity.MEDIUM
    )
    assert (
        IncidentSeverityRegistry.calculate_severity([AlertSeverity.LOW])
        == IncidentSeverity.LOW
    )


def test_incident_fingerprint_stability() -> None:
    """Verify incident fingerprint calculation stability."""
    alert_ids = [uuid.uuid4(), uuid.uuid4()]
    asset_ids = [uuid.uuid4()]
    finding_ids = [uuid.uuid4()]

    fp1 = IncidentFingerprintService.generate_fingerprint(
        alert_ids, asset_ids, finding_ids
    )
    # Reverse list order to test sorting stability
    fp2 = IncidentFingerprintService.generate_fingerprint(
        list(reversed(alert_ids)), asset_ids, finding_ids
    )
    assert fp1 == fp2


def test_incident_history_preservation() -> None:
    """Verify history log entries are immutable and append correctly."""
    iid = uuid.uuid4()
    IncidentHistoryService.record_event(iid, "CREATED", "First event")
    IncidentHistoryService.record_event(iid, "ASSIGNED", "Second event")

    history = IncidentHistoryService.get_history(iid)
    assert len(history) == 2
    assert history[0].event_type == "CREATED"
    assert history[1].event_type == "ASSIGNED"


def test_incident_evidence_stability() -> None:
    """Verify evidence references are read-only and retain original snapshots."""
    iid = uuid.uuid4()

    class DummyAlert:
        def __init__(self, alert_id, severity):
            self.alert_id = alert_id
            self.severity = severity

        def copy(self):
            return DummyAlert(self.alert_id, self.severity)

    alert_id = uuid.uuid4()
    ent = DummyAlert(alert_id, "HIGH")
    IncidentEvidenceService.add_evidence(iid, "alerts", ent)

    # Check if duplicate is ignored
    ent2 = DummyAlert(alert_id, "CRITICAL")
    IncidentEvidenceService.add_evidence(iid, "alerts", ent2)

    evidence = IncidentEvidenceService.get_evidence(iid)
    assert len(evidence["alerts"]) == 1
    # Preserve original severity snapshot
    assert evidence["alerts"][0].severity == "HIGH"


@pytest.mark.asyncio
async def test_incident_sync(mock_db, mock_asset, mock_finding) -> None:
    """Verify that sync_alerts reconciles alerts into unified incidents."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # Seed open alerts
    alert = AlertRecord(
        alert_id=uuid.uuid4(),
        alert_fingerprint="fp-1",
        alert_type=AlertType.CRITICAL_FINDING,
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.OPEN,
        title="critical alert",
        description="description",
        asset_id=ASSET_ID,
        finding_id=FINDING_ID,
    )
    AlertLifecycleService._alerts[alert.alert_id] = alert
    AlertLifecycleService._fingerprint_lookup["fp-1"] = alert.alert_id

    await IncidentService.sync_alerts(mock_db)
    incidents = IncidentService.get_all_incidents()
    assert len(incidents) == 1
    assert incidents[0].severity == IncidentSeverity.CRITICAL
    assert len(incidents[0].alert_ids) == 1


@pytest.mark.asyncio
async def test_incident_sync_deduplication(mock_db, mock_asset, mock_finding) -> None:
    """Verify synchronization deduplication leaves existing incidents intact."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    alert = AlertRecord(
        alert_id=uuid.uuid4(),
        alert_fingerprint="fp-1",
        alert_type=AlertType.CRITICAL_FINDING,
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.OPEN,
        title="critical alert",
        description="description",
        asset_id=ASSET_ID,
        finding_id=FINDING_ID,
    )
    AlertLifecycleService._alerts[alert.alert_id] = alert
    AlertLifecycleService._fingerprint_lookup["fp-1"] = alert.alert_id

    await IncidentService.sync_alerts(mock_db)
    assert len(IncidentService.get_all_incidents()) == 1

    # Rerun sync alert processing
    await IncidentService.sync_alerts(mock_db)
    assert len(IncidentService.get_all_incidents()) == 1


@pytest.mark.asyncio
async def test_incident_state_transitions(mock_db) -> None:
    """Verify designed state machine transitions for incidents."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.OPEN,
    )
    IncidentService._incidents[iid] = inc

    # OPEN -> TRIAGED
    await IncidentService.transition_status(mock_db, iid, IncidentStatus.TRIAGED)
    assert inc.status == IncidentStatus.TRIAGED

    # TRIAGED -> INVESTIGATING
    await IncidentService.transition_status(mock_db, iid, IncidentStatus.INVESTIGATING)
    assert inc.status == IncidentStatus.INVESTIGATING

    # Invalid: INVESTIGATING -> CLOSED
    with pytest.raises(ValueError):
        await IncidentService.transition_status(mock_db, iid, IncidentStatus.CLOSED)


@pytest.mark.asyncio
async def test_closed_incident_enforcement(mock_db) -> None:
    """Verify CLOSED state is terminal and blocks all mutations."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.CLOSED,
    )
    IncidentService._incidents[iid] = inc

    # Try to reopen or transition status
    with pytest.raises(ValueError):
        await IncidentService.transition_status(mock_db, iid, IncidentStatus.OPEN)

    # Try to assign
    with pytest.raises(ValueError):
        await IncidentService.assign_incident(mock_db, iid, uuid.uuid4())

    # Try to add notes
    with pytest.raises(ValueError):
        await InvestigationService.add_investigation_note(
            mock_db, iid, uuid.uuid4(), "notes"
        )


@pytest.mark.asyncio
async def test_incident_assignment(mock_db) -> None:
    """Verify assign_incident logs assignment history."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.OPEN,
    )
    IncidentService._incidents[iid] = inc

    owner_id = uuid.uuid4()
    await IncidentService.assign_incident(mock_db, iid, owner_id)
    assert inc.owner == owner_id
    history = IncidentHistoryService.get_history(iid)
    assert history[0].event_type == "ASSIGNED"


@pytest.mark.asyncio
async def test_incident_escalation_manual_team(mock_db) -> None:
    """Verify manual escalation to a team works and logs history."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.TRIAGED,
    )
    IncidentService._incidents[iid] = inc

    await IncidentEscalationService.escalate_to_team(mock_db, iid, "SOC-L3")
    assert inc.status == IncidentStatus.ESCALATED
    history = IncidentHistoryService.get_history(iid)
    assert any(h.event_type == "ESCALATED" for h in history)
    assert any("SOC-L3" in h.details for h in history)


@pytest.mark.asyncio
async def test_incident_escalation_manual_owner(mock_db) -> None:
    """Verify manual escalation to owner works and logs history."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.TRIAGED,
    )
    IncidentService._incidents[iid] = inc

    owner_id = uuid.uuid4()
    await IncidentEscalationService.escalate_to_owner(mock_db, iid, owner_id)
    assert inc.status == IncidentStatus.ESCALATED
    assert inc.owner == owner_id


@pytest.mark.asyncio
async def test_incident_escalation_manual_management(mock_db) -> None:
    """Verify manual escalation to management works and logs history."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.TRIAGED,
    )
    IncidentService._incidents[iid] = inc

    await IncidentEscalationService.escalate_to_management(mock_db, iid)
    assert inc.status == IncidentStatus.ESCALATED


@pytest.mark.asyncio
async def test_incident_escalation_auto_sla(mock_db) -> None:
    """Verify auto-escalation check tasks trigger on SLA breaches."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    iid = uuid.uuid4()
    # Age greater than 1 hour for CRITICAL severity
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.OPEN,
        created_at=old_time,
    )
    IncidentService._incidents[iid] = inc

    await IncidentEscalationService.process_escalations(mock_db)
    assert inc.status == IncidentStatus.ESCALATED
    history = IncidentHistoryService.get_history(iid)
    assert any(h.event_type == "AUTO_ESCALATED" for h in history)


def test_incident_snapshot_cache() -> None:
    """Verify snapshot regeneration and caching."""
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.OPEN,
    )
    IncidentService._incidents[iid] = inc

    snap = IncidentSnapshotService.get_snapshot()
    assert snap["total"] == 1
    assert snap["critical"] == 1

    # Invalidate and check
    IncidentSnapshotService.invalidate_cache()
    assert IncidentSnapshotService._global_snapshot is None
    snap2 = IncidentSnapshotService.get_snapshot()
    assert snap2["total"] == 1


# --- API Routes Verification ---


@pytest.mark.asyncio
async def test_api_list_incidents(client, mock_admin, mock_operator, mock_db) -> None:
    """Verify list incidents endpoints filter by allowed scopes."""
    # Seed incident
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc

    # Admin retrieve -> returns all
    headers_admin = get_auth_header(ADMIN_ID, "admin")
    res_admin = await client.get("/api/v1/incidents", headers=headers_admin)
    assert res_admin.status_code == 200
    assert len(res_admin.json()) == 1

    # Operator retrieve -> filters asset scope
    headers_op = get_auth_header(OPERATOR_ID, "operator")
    # Empty db mock execution returns empty scope
    mock_db.execute = AsyncMock(return_value=MagicMock())
    res_op = await client.get("/api/v1/incidents", headers=headers_op)
    assert res_op.status_code == 200
    assert len(res_op.json()) == 0


@pytest.mark.asyncio
async def test_api_get_incident(
    client, mock_admin, mock_operator, mock_db, mock_asset
) -> None:
    """Verify retrieve details checks scope access permissions."""
    setup_basic_mock_db(mock_db, mock_asset, None)
    # Seed incident
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc

    # Admin access -> allowed
    headers_admin = get_auth_header(ADMIN_ID, "admin")
    res_admin = await client.get(f"/api/v1/incidents/{iid}", headers=headers_admin)
    assert res_admin.status_code == 200

    # Operator access scope check -> blocked if not matching scope
    headers_op = get_auth_header(OPERATOR_ID, "operator")
    mock_db.execute = AsyncMock(return_value=MagicMock())
    res_op = await client.get(f"/api/v1/incidents/{iid}", headers=headers_op)
    assert res_op.status_code == 403


@pytest.mark.asyncio
async def test_api_assign_incident(client, mock_admin, mock_db) -> None:
    """Verify API assignment updates owner."""
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc

    # Mock user exists
    target_user = User()
    target_user.id = OPERATOR_ID
    target_user.deleted_at = None
    mock_db.get = AsyncMock(return_value=target_user)
    mock_db.commit = AsyncMock()

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.post(
        f"/api/v1/incidents/{iid}/assign",
        json={"owner_id": str(OPERATOR_ID)},
        headers=headers,
    )
    assert res.status_code == 200
    assert inc.owner == OPERATOR_ID


@pytest.mark.asyncio
async def test_api_triage_incident(client, mock_admin, mock_db) -> None:
    """Verify triage transition."""
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc
    mock_db.commit = AsyncMock()

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.post(f"/api/v1/incidents/{iid}/triage", headers=headers)
    assert res.status_code == 200
    assert inc.status == IncidentStatus.TRIAGED


@pytest.mark.asyncio
async def test_api_start_incident(client, mock_admin, mock_db) -> None:
    """Verify start investigation transition."""
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.TRIAGED,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc
    mock_db.commit = AsyncMock()

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.post(
        f"/api/v1/incidents/{iid}/start",
        json={"notes": "starting investigation"},
        headers=headers,
    )
    assert res.status_code == 200
    assert inc.status == IncidentStatus.INVESTIGATING


@pytest.mark.asyncio
async def test_api_contain_incident(client, mock_admin, mock_db) -> None:
    """Verify contain transition."""
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.INVESTIGATING,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc
    mock_db.commit = AsyncMock()

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.post(
        f"/api/v1/incidents/{iid}/contain",
        json={"notes": "containing incident"},
        headers=headers,
    )
    assert res.status_code == 200
    assert inc.status == IncidentStatus.CONTAINED


@pytest.mark.asyncio
async def test_api_resolve_incident(client, mock_admin, mock_db) -> None:
    """Verify resolve transition."""
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.CONTAINED,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc
    mock_db.commit = AsyncMock()

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.post(f"/api/v1/incidents/{iid}/resolve", headers=headers)
    assert res.status_code == 200
    assert inc.status == IncidentStatus.RESOLVED


@pytest.mark.asyncio
async def test_api_close_incident(client, mock_admin, mock_db) -> None:
    """Verify close transition."""
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.RESOLVED,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc
    mock_db.commit = AsyncMock()

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.post(f"/api/v1/incidents/{iid}/close", headers=headers)
    assert res.status_code == 200
    assert inc.status == IncidentStatus.CLOSED


@pytest.mark.asyncio
async def test_api_timeline(client, mock_admin, mock_db) -> None:
    """Verify timeline retrieve."""
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc

    IncidentHistoryService.record_event(iid, "CREATED", "First event")

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.get(f"/api/v1/incidents/{iid}/timeline", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["event_type"] == "CREATED"


@pytest.mark.asyncio
async def test_api_evidence(client, mock_admin, mock_db) -> None:
    """Verify evidence snapshots retrieve."""
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc

    class DummyAlert:
        def __init__(self, alert_id, status):
            self.alert_id = alert_id
            self.status = status

        def copy(self):
            return DummyAlert(self.alert_id, self.status)

    alert_id = uuid.uuid4()
    IncidentEvidenceService.add_evidence(iid, "alerts", DummyAlert(alert_id, "OPEN"))

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.get(f"/api/v1/incidents/{iid}/evidence", headers=headers)
    assert res.status_code == 200
    assert "alerts" in res.json()
    assert len(res.json()["alerts"]) == 1


@pytest.mark.asyncio
async def test_api_add_note(client, mock_admin, mock_db) -> None:
    """Verify note logging entry endpoints."""
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.post(
        f"/api/v1/incidents/{iid}/notes",
        json={"notes": "investigation note", "analyst": "admin"},
        headers=headers,
    )
    assert res.status_code == 200
    entries = InvestigationService.get_investigation_timeline(iid)
    assert len(entries) == 1
    assert entries[0].notes == "investigation note"


@pytest.mark.asyncio
async def test_api_escalate_team(client, mock_admin, mock_db) -> None:
    """Verify team manual escalation endpoint."""
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.TRIAGED,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc
    mock_db.commit = AsyncMock()

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.post(
        f"/api/v1/incidents/{iid}/escalate/team",
        json={"team": "SOC-L3"},
        headers=headers,
    )
    assert res.status_code == 200
    assert inc.status == IncidentStatus.ESCALATED


@pytest.mark.asyncio
async def test_api_escalate_owner(client, mock_admin, mock_db) -> None:
    """Verify owner manual escalation endpoint."""
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.TRIAGED,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc

    target_user = User()
    target_user.id = OPERATOR_ID
    target_user.deleted_at = None
    mock_db.get = AsyncMock(return_value=target_user)
    mock_db.commit = AsyncMock()

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.post(
        f"/api/v1/incidents/{iid}/escalate/owner",
        json={"owner_id": str(OPERATOR_ID)},
        headers=headers,
    )
    assert res.status_code == 200
    assert inc.status == IncidentStatus.ESCALATED
    assert inc.owner == OPERATOR_ID


@pytest.mark.asyncio
async def test_api_escalate_management(client, mock_admin, mock_db) -> None:
    """Verify management manual escalation endpoint."""
    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.TRIAGED,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc
    mock_db.commit = AsyncMock()

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.post(
        f"/api/v1/incidents/{iid}/escalate/management",
        headers=headers,
    )
    assert res.status_code == 200
    assert inc.status == IncidentStatus.ESCALATED


@pytest.mark.asyncio
async def test_ai_context_incident_injection(mock_db, mock_asset) -> None:
    """Verify incident context injections into context builders."""
    setup_basic_mock_db(mock_db, mock_asset, None)

    iid = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=iid,
        incident_fingerprint="fp-inc",
        title="Test Inc",
        description="Desc",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[iid] = inc

    ctx = await AIContextBuilder.build_incident_context(mock_db, iid)
    assert ctx["incident_id"] == str(iid)
    assert "incident_timeline" in ctx
    assert "linked_evidence" in ctx
