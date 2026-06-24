import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from src.core.security import create_access_token
from src.domain.entities.alert import AlertSeverity, AlertStatus, AlertType
from src.infrastructure.database.models import Asset, Finding, Scope, User, Workflow
from src.services.ai_context_builder import AIContextBuilder
from src.services.alert_escalation_service import AlertEscalationService
from src.services.alert_fingerprint_service import AlertFingerprintService
from src.services.alert_generation_service import AlertGenerationService
from src.services.alert_lifecycle_service import AlertLifecycleService, AlertRecord
from src.services.alert_queue_service import AlertQueueService
from src.services.alert_severity_registry import AlertSeverityRegistry
from src.services.alert_snapshot_service import AlertSnapshotService
from src.services.continuous_refresh_service import ContinuousRefreshService
from src.services.remediation_service import RemediationRecord

ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OPERATOR_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
SCOPE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
ASSET_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
FINDING_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
REMEDIATION_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")


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
    s.definition = {"domains": ["test.com"]}
    s.created_at = datetime.now(timezone.utc)
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


@pytest.fixture
def mock_remediation() -> RemediationRecord:
    from src.domain.entities.remediation import RemediationStatus

    r = RemediationRecord(
        remediation_id=REMEDIATION_ID,
        recommendation_fingerprint="remedi-fp",
        asset_id=ASSET_ID,
        finding_id=FINDING_ID,
        status=RemediationStatus.OPEN,
        due_date=datetime.now(timezone.utc) - timedelta(days=1),
        created_at=datetime.now(timezone.utc) - timedelta(days=10),
        updated_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    return r


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_stores():
    ContinuousRefreshService.clear_events()
    AlertLifecycleService.clear_alerts()
    AlertSnapshotService.clear_snapshots()


def setup_basic_mock_db(mock_db, mock_asset, mock_finding):
    mock_db.get = AsyncMock(
        side_effect=lambda model, ident: (
            mock_asset
            if model == Asset
            else (mock_finding if model == Finding else None)
        )
    )


# --- Tests ---


def test_alert_fingerprint_stability() -> None:
    """Verify alert fingerprint is stable across lifecycle, owner, and severity changes."""
    fp1 = AlertFingerprintService.calculate_fingerprint(
        alert_type="ASSET_DRIFT",
        asset_id=ASSET_ID,
        finding_id=None,
    )
    fp2 = AlertFingerprintService.calculate_fingerprint(
        alert_type="ASSET_DRIFT",
        asset_id=ASSET_ID,
        finding_id=None,
    )
    assert fp1 == fp2

    # Different type -> different fingerprint
    fp3 = AlertFingerprintService.calculate_fingerprint(
        alert_type="FINDING_DRIFT",
        asset_id=ASSET_ID,
        finding_id=FINDING_ID,
    )
    assert fp1 != fp3


def test_alert_severity_registry() -> None:
    """Verify registry maps AlertTypes to correct AlertSeverities."""
    assert (
        AlertSeverityRegistry.get_severity(AlertType.CRITICAL_FINDING)
        == AlertSeverity.CRITICAL
    )
    assert (
        AlertSeverityRegistry.get_severity(AlertType.SLA_BREACH) == AlertSeverity.HIGH
    )
    assert (
        AlertSeverityRegistry.get_severity(AlertType.ASSET_DRIFT) == AlertSeverity.LOW
    )


@pytest.mark.asyncio
async def test_alert_generation(mock_db) -> None:
    """Verify alerts are correctly created from Continuous Monitoring drift events."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)

    # Emit a monitoring event
    await ContinuousRefreshService.emit_event(
        db=mock_db,
        change_type="ASSET_ADDED",
        asset_id=ASSET_ID,
        finding_id=None,
        previous_state=None,
        current_state="{}",
    )

    # Generate alerts
    await AlertGenerationService.generate_alerts(mock_db)

    alerts = AlertLifecycleService.get_all_alerts()
    assert len(alerts) == 1
    assert alerts[0].alert_type == AlertType.ASSET_DRIFT
    assert alerts[0].status == AlertStatus.OPEN
    assert alerts[0].severity == AlertSeverity.LOW


@pytest.mark.asyncio
async def test_alert_deduplication(mock_db) -> None:
    """Verify that multiple alert generation runs do not duplicate existing alerts."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)

    await ContinuousRefreshService.emit_event(
        db=mock_db,
        change_type="ASSET_ADDED",
        asset_id=ASSET_ID,
        finding_id=None,
        previous_state=None,
        current_state="{}",
    )

    await AlertGenerationService.generate_alerts(mock_db)
    assert len(AlertLifecycleService.get_all_alerts()) == 1

    # Repeat generation
    await AlertGenerationService.generate_alerts(mock_db)
    assert len(AlertLifecycleService.get_all_alerts()) == 1


@pytest.mark.asyncio
async def test_alert_terminal_state_enforcement(mock_db) -> None:
    """Verify terminal alert status cannot transition or be reopened by refresh cycles."""
    # Seed an alert
    alert_id = uuid.uuid4()
    alert = AlertRecord(
        alert_id=alert_id,
        alert_fingerprint="test-fp",
        alert_type=AlertType.ASSET_DRIFT,
        severity=AlertSeverity.LOW,
        status=AlertStatus.OPEN,
        title="Drift",
        description="Drift",
        asset_id=ASSET_ID,
    )
    AlertLifecycleService._alerts[alert_id] = alert
    AlertLifecycleService._fingerprint_lookup["test-fp"] = alert_id

    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # Move to terminal RESOLVED state
    await AlertLifecycleService.transition_alert(
        mock_db, alert_id, AlertStatus.ACKNOWLEDGED
    )
    await AlertLifecycleService.transition_alert(
        mock_db, alert_id, AlertStatus.IN_PROGRESS
    )
    await AlertLifecycleService.transition_alert(
        mock_db, alert_id, AlertStatus.RESOLVED
    )

    # Try transitioning out of terminal status -> ValueError
    with pytest.raises(ValueError, match="Cannot transition from terminal state"):
        await AlertLifecycleService.transition_alert(
            mock_db, alert_id, AlertStatus.OPEN
        )


@pytest.mark.asyncio
async def test_alert_auto_resolution_finding(mock_db) -> None:
    """Verify that resolving a finding auto-resolves its corresponding FINDING_DRIFT alert."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)

    # Seed alert
    alert_id = uuid.uuid4()
    alert = AlertRecord(
        alert_id=alert_id,
        alert_fingerprint="f-fp",
        alert_type=AlertType.FINDING_DRIFT,
        severity=AlertSeverity.MEDIUM,
        status=AlertStatus.OPEN,
        title="Drift",
        description="Drift",
        asset_id=ASSET_ID,
        finding_id=FINDING_ID,
    )
    AlertLifecycleService._alerts[alert_id] = alert
    AlertLifecycleService._fingerprint_lookup["f-fp"] = alert_id

    # Emit finding resolved event
    await ContinuousRefreshService.emit_event(
        db=mock_db,
        change_type="FINDING_RESOLVED",
        asset_id=ASSET_ID,
        finding_id=FINDING_ID,
        previous_state=None,
        current_state="{}",
    )

    await AlertGenerationService.generate_alerts(mock_db)
    assert AlertLifecycleService.get_alert(alert_id).status == AlertStatus.RESOLVED


@pytest.mark.asyncio
async def test_alert_auto_resolution_compliance(mock_db) -> None:
    """Verify that compliance restoration auto-resolves COMPLIANCE_DRIFT alerts."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)

    # Seed alert
    alert_id = uuid.uuid4()
    alert = AlertRecord(
        alert_id=alert_id,
        alert_fingerprint="c-fp",
        alert_type=AlertType.COMPLIANCE_DRIFT,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        title="Drift",
        description="Drift",
        asset_id=ASSET_ID,
    )
    AlertLifecycleService._alerts[alert_id] = alert
    AlertLifecycleService._fingerprint_lookup["c-fp"] = alert_id

    await ContinuousRefreshService.emit_event(
        db=mock_db,
        change_type="COMPLIANCE_RESTORED",
        asset_id=ASSET_ID,
        finding_id=None,
        previous_state=None,
        current_state="{}",
    )

    await AlertGenerationService.generate_alerts(mock_db)
    assert AlertLifecycleService.get_alert(alert_id).status == AlertStatus.RESOLVED


@pytest.mark.asyncio
async def test_alert_auto_resolution_sla(mock_db, mock_remediation) -> None:
    """Verify that remediating/resolving SLA overdue items auto-resolves SLA_BREACH alerts."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # Seed alert
    alert_id = uuid.uuid4()
    alert = AlertRecord(
        alert_id=alert_id,
        alert_fingerprint="s-fp",
        alert_type=AlertType.SLA_BREACH,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        title="Drift",
        description="Drift",
        asset_id=ASSET_ID,
        remediation_id=REMEDIATION_ID,
    )
    AlertLifecycleService._alerts[alert_id] = alert
    AlertLifecycleService._fingerprint_lookup["s-fp"] = alert_id

    # Mock no active overdue items (SLA breached items)
    with patch(
        "src.services.remediation_aging_service.RemediationAgingService.get_overdue_items",
        return_value=[],
    ):
        await AlertGenerationService.generate_alerts(mock_db)
        assert AlertLifecycleService.get_alert(alert_id).status == AlertStatus.RESOLVED


@pytest.mark.asyncio
async def test_alert_lifecycle_transitions(mock_db) -> None:
    """Verify alert status machine sequence rules and invalid transitions rejection."""
    alert_id = uuid.uuid4()
    alert = AlertRecord(
        alert_id=alert_id,
        alert_fingerprint="fp-lc",
        alert_type=AlertType.ASSET_DRIFT,
        severity=AlertSeverity.LOW,
        status=AlertStatus.OPEN,
        title="Drift",
        description="Drift",
        asset_id=ASSET_ID,
    )
    AlertLifecycleService._alerts[alert_id] = alert
    AlertLifecycleService._fingerprint_lookup["fp-lc"] = alert_id

    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # Open -> In Progress directly is invalid
    with pytest.raises(ValueError, match="Invalid transition"):
        await AlertLifecycleService.transition_alert(
            mock_db, alert_id, AlertStatus.IN_PROGRESS
        )

    # Valid: Open -> Acknowledged
    await AlertLifecycleService.transition_alert(
        mock_db, alert_id, AlertStatus.ACKNOWLEDGED
    )
    assert alert.status == AlertStatus.ACKNOWLEDGED

    # Valid: Acknowledged -> In Progress
    await AlertLifecycleService.transition_alert(
        mock_db, alert_id, AlertStatus.IN_PROGRESS
    )
    assert alert.status == AlertStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_alert_assignment(mock_db) -> None:
    """Verify analyst assignment sets the owner and generates history/audit logging."""
    alert_id = uuid.uuid4()
    alert = AlertRecord(
        alert_id=alert_id,
        alert_fingerprint="fp-as",
        alert_type=AlertType.ASSET_DRIFT,
        severity=AlertSeverity.LOW,
        status=AlertStatus.OPEN,
        title="Drift",
        description="Drift",
        asset_id=ASSET_ID,
    )
    AlertLifecycleService._alerts[alert_id] = alert
    AlertLifecycleService._fingerprint_lookup["fp-as"] = alert_id

    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    owner_id = uuid.uuid4()
    await AlertLifecycleService.assign_alert(mock_db, alert_id, owner_id)
    assert alert.owner == owner_id
    assert any(h["type"] == "OWNER_CHANGE" for h in alert.history)


def test_alert_queue_stats() -> None:
    """Verify queue metrics calculations are correct."""
    alert_id1 = uuid.uuid4()
    alert1 = AlertRecord(
        alert_id=alert_id1,
        alert_fingerprint="q1",
        alert_type=AlertType.ASSET_DRIFT,
        severity=AlertSeverity.LOW,
        status=AlertStatus.OPEN,
        title="Drift",
        description="Drift",
        asset_id=ASSET_ID,
    )
    AlertLifecycleService._alerts[alert_id1] = alert1

    alert_id2 = uuid.uuid4()
    alert2 = AlertRecord(
        alert_id=alert_id2,
        alert_fingerprint="q2",
        alert_type=AlertType.CRITICAL_FINDING,
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.ESCALATED,
        title="Drift",
        description="Drift",
        asset_id=ASSET_ID,
    )
    AlertLifecycleService._alerts[alert_id2] = alert2

    stats = AlertQueueService.get_queue_stats()
    assert stats["open_alerts"] == 1
    assert stats["escalated_alerts"] == 1
    assert stats["total_active_alerts"] == 2


@pytest.mark.asyncio
async def test_alert_escalation_service(mock_db) -> None:
    """Verify that older alerts breach severity aging limits and auto-escalate."""
    alert_id = uuid.uuid4()
    # Past creation threshold: LOW alert needs 14 days, let's backdate it to 15 days ago
    backdated = datetime.now(timezone.utc) - timedelta(days=15)
    alert = AlertRecord(
        alert_id=alert_id,
        alert_fingerprint="esc-fp",
        alert_type=AlertType.ASSET_DRIFT,
        severity=AlertSeverity.LOW,
        status=AlertStatus.OPEN,
        title="Drift",
        description="Drift",
        asset_id=ASSET_ID,
        created_at=backdated,
    )
    AlertLifecycleService._alerts[alert_id] = alert
    AlertLifecycleService._fingerprint_lookup["esc-fp"] = alert_id

    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    escalated = await AlertEscalationService.process_escalations(mock_db)
    assert len(escalated) == 1
    assert alert.status == AlertStatus.ESCALATED
    assert len(alert.escalation_history) == 1


def test_alert_snapshot_rebuild_consistency() -> None:
    """Verify alert snapshot generates dynamically from raw cache items when cache cleared."""
    alert_id = uuid.uuid4()
    alert = AlertRecord(
        alert_id=alert_id,
        alert_fingerprint="snap-fp",
        alert_type=AlertType.CRITICAL_FINDING,
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.OPEN,
        title="Drift",
        description="Drift",
        asset_id=ASSET_ID,
    )
    AlertLifecycleService._alerts[alert_id] = alert

    AlertSnapshotService.clear_snapshots()

    snap = AlertSnapshotService.get_snapshot()
    assert snap["total_alerts"] == 1
    assert snap["severity_counts"]["CRITICAL"] == 1
    assert snap["status_counts"]["OPEN"] == 1


# --- API Endpoint Integration Tests ---


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.alerts.get_scope_by_id")
async def test_alerts_api_list(
    mock_get_scope,
    mock_get_user,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
    mock_asset: Asset,
    mock_db: AsyncMock,
) -> None:
    """Verify GET /api/v1/alerts lists user scope-filtered alerts successfully."""
    mock_get_user.return_value = mock_operator
    mock_get_scope.return_value = mock_scope

    mock_db.get = AsyncMock(
        side_effect=lambda model, ident: mock_asset if model == Asset else None
    )

    # Seed scopes & assets in DB
    mock_res_scopes = MagicMock()
    mock_res_scopes.scalars.return_value.all.return_value = [mock_scope]
    mock_res_assets = MagicMock()
    mock_res_assets.scalars.return_value.all.return_value = [mock_asset.id]

    def db_execute_side_effect(query, *args, **kwargs):
        column_desc = getattr(query, "column_descriptions", [])
        if column_desc:
            entity = column_desc[0].get("entity")
            if entity == Scope:
                return mock_res_scopes
            elif entity == Asset:
                return mock_res_assets
        q_str = str(query).lower()
        if "scope" in q_str and "asset" not in q_str:
            return mock_res_scopes
        return mock_res_assets

    mock_db.execute = AsyncMock(side_effect=db_execute_side_effect)

    # Seed alert
    alert_id = uuid.uuid4()
    alert = AlertRecord(
        alert_id=alert_id,
        alert_fingerprint="api-fp",
        alert_type=AlertType.ASSET_DRIFT,
        severity=AlertSeverity.LOW,
        status=AlertStatus.OPEN,
        title="Drift",
        description="Drift",
        asset_id=ASSET_ID,
    )
    AlertLifecycleService._alerts[alert_id] = alert

    headers = get_auth_header(OPERATOR_ID, "operator")
    res = await client.get("/api/v1/alerts", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.alerts.get_scope_by_id")
async def test_alerts_api_scope_violations_blocked(
    mock_get_scope,
    mock_get_user,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
    mock_asset: Asset,
    mock_db: AsyncMock,
) -> None:
    """Verify operators are forbidden from viewing or mutating alerts outside scope."""
    mock_get_user.return_value = mock_operator

    # Scope ownership mismatch
    mock_scope.owner_id = uuid.uuid4()
    mock_get_scope.return_value = mock_scope

    mock_db.get = AsyncMock(
        side_effect=lambda model, ident: mock_asset if model == Asset else None
    )

    alert_id = uuid.uuid4()
    alert = AlertRecord(
        alert_id=alert_id,
        alert_fingerprint="forbidden-fp",
        alert_type=AlertType.ASSET_DRIFT,
        severity=AlertSeverity.LOW,
        status=AlertStatus.OPEN,
        title="Drift",
        description="Drift",
        asset_id=ASSET_ID,
    )
    AlertLifecycleService._alerts[alert_id] = alert

    headers = get_auth_header(OPERATOR_ID, "operator")
    res = await client.get(f"/api/v1/alerts/{alert_id}", headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.alerts.get_scope_by_id")
async def test_alerts_api_transition_actions(
    mock_get_scope,
    mock_get_user,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
    mock_asset: Asset,
    mock_db: AsyncMock,
) -> None:
    """Verify POST actions transition alerts correctly through the state machine."""
    mock_get_user.return_value = mock_operator
    mock_get_scope.return_value = mock_scope

    mock_db.get = AsyncMock(
        side_effect=lambda model, ident: mock_asset if model == Asset else None
    )

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res_wf = MagicMock()
    mock_res_wf.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res_wf)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    alert_id = uuid.uuid4()
    alert = AlertRecord(
        alert_id=alert_id,
        alert_fingerprint="transition-fp",
        alert_type=AlertType.ASSET_DRIFT,
        severity=AlertSeverity.LOW,
        status=AlertStatus.OPEN,
        title="Drift",
        description="Drift",
        asset_id=ASSET_ID,
    )
    AlertLifecycleService._alerts[alert_id] = alert

    headers = get_auth_header(OPERATOR_ID, "operator")

    # Acknowledge
    res_ack = await client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge", headers=headers
    )
    assert res_ack.status_code == 200
    assert alert.status == AlertStatus.ACKNOWLEDGED

    # Start
    res_start = await client.post(f"/api/v1/alerts/{alert_id}/start", headers=headers)
    assert res_start.status_code == 200
    assert alert.status == AlertStatus.IN_PROGRESS

    # Resolve
    res_res = await client.post(f"/api/v1/alerts/{alert_id}/resolve", headers=headers)
    assert res_res.status_code == 200
    assert alert.status == AlertStatus.RESOLVED


@pytest.mark.asyncio
async def test_celery_task_alert_integration(mock_db) -> None:
    """Verify the Celery worker calls alert generation and escalation checks dynamically."""
    from src.infrastructure.celery.worker import _execute_workflow_async
    from src.infrastructure.database.models import ScanRun, Scope, Workflow

    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # Mock DB entities
    owner_id = uuid.uuid4()
    mock_wf = Workflow(
        id=uuid.uuid4(),
        owner_id=owner_id,
        definition={"steps": [{"type": "discovery"}]},
        created_at=datetime.now(timezone.utc),
    )
    mock_run = ScanRun(
        id=uuid.uuid4(),
        status="pending",
        workflow_id=mock_wf.id,
    )
    mock_scope = Scope(
        id=SCOPE_ID,
        owner_id=owner_id,
        deleted_at=None,
    )

    mock_db.get = AsyncMock(side_effect=[mock_wf, mock_run, mock_scope])

    mock_res_assets = MagicMock()
    mock_res_assets.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_res_assets)

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db

    with patch(
        "src.services.continuous_refresh_service.ContinuousRefreshService.refresh_all"
    ) as mock_refresh, patch(
        "src.services.alert_generation_service.AlertGenerationService.generate_alerts"
    ) as mock_gen, patch(
        "src.services.alert_escalation_service.AlertEscalationService.process_escalations"
    ) as mock_esc, patch(
        "src.infrastructure.celery.worker.AsyncSessionLocal", mock_session_factory
    ):

        # Execute celery task helper
        await _execute_workflow_async(mock_wf.id, mock_run.id, SCOPE_ID)

        assert mock_refresh.called
        assert mock_gen.called
        assert mock_esc.called


@pytest.mark.asyncio
async def test_ai_context_alert_injection(mock_db, mock_asset) -> None:
    """Verify the AI prompt context builder correctly aggregates and formats alert metrics."""
    setup_basic_mock_db(mock_db, mock_asset, None)

    alert_id = uuid.uuid4()
    alert = AlertRecord(
        alert_id=alert_id,
        alert_fingerprint="ai-fp",
        alert_type=AlertType.CRITICAL_FINDING,
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.OPEN,
        title="Drift",
        description="Drift",
        asset_id=ASSET_ID,
    )
    AlertLifecycleService._alerts[alert_id] = alert

    with patch(
        "src.services.asset_report_service.AssetReportService.generate_asset_report",
        return_value={
            "asset": {},
            "ports": [],
            "services": [],
            "technologies": [],
            "risk": {},
            "findings": [],
            "exposure": {},
        },
    ), patch(
        "src.services.recommendation_service.RecommendationService.generate_asset_recommendations",
        return_value=[],
    ), patch(
        "src.services.recommendation_snapshot_service.RecommendationSnapshotService.get_snapshot",
        return_value={},
    ), patch(
        "src.services.remediation_snapshot_service.RemediationSnapshotService.get_snapshot",
        return_value={},
    ), patch(
        "src.services.governance_service.GovernanceService.evaluate_asset_governance",
        return_value=MagicMock(value="COMPLIANT"),
    ), patch(
        "src.services.risk_acceptance_service.RiskAcceptanceService.get_acceptances_by_asset",
        return_value=[],
    ), patch(
        "src.services.compliance_mapping_service.ComplianceMappingService.get_compliance_controls",
        return_value=[],
    ):

        ctx = await AIContextBuilder.build_asset_context(mock_db, ASSET_ID)

        assert "alert_summary" in ctx
        assert "active_alerts" in ctx
        assert ctx["critical_alerts"] == 1
        assert ctx["alert_summary"]["total_active_alerts"] == 1
