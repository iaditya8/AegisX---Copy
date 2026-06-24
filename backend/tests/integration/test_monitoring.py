import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from src.core.security import create_access_token
from src.domain.entities.governance import GovernanceStatus
from src.infrastructure.database.models import Asset, Finding, Scope, User, Workflow
from src.services.baseline_state_service import BaselineStateService
from src.services.continuous_refresh_service import ContinuousRefreshService
from src.services.monitoring_snapshot_service import MonitoringSnapshotService

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


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_stores():
    ContinuousRefreshService.clear_events()
    BaselineStateService.clear_baselines()
    MonitoringSnapshotService.clear_snapshots()


def setup_basic_mock_db(mock_db, mock_asset, mock_finding):
    mock_db.get = AsyncMock(
        side_effect=lambda model, ident: (
            mock_asset
            if model == Asset
            else (mock_finding if model == Finding else None)
        )
    )


# --- Integration Tests ---


@pytest.mark.asyncio
async def test_event_fingerprint_deduplication(mock_db, mock_asset) -> None:
    """Verify identical events are deduplicated based on fingerprint."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)

    e1 = await ContinuousRefreshService.emit_event(
        db=mock_db,
        change_type="ASSET_ADDED",
        asset_id=ASSET_ID,
        finding_id=None,
        previous_state=None,
        current_state="test-state",
    )
    e2 = await ContinuousRefreshService.emit_event(
        db=mock_db,
        change_type="ASSET_ADDED",
        asset_id=ASSET_ID,
        finding_id=None,
        previous_state=None,
        current_state="test-state",
    )

    assert e1 is not None
    assert e2 == e1
    assert len(ContinuousRefreshService.get_all_events()) == 1


@pytest.mark.asyncio
async def test_baseline_dynamic_rebuild(mock_db, mock_asset) -> None:
    """Verify baseline caches reconstruct themselves from events history if lost."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)

    asset_data = {"host": "test.com", "ip": "192.168.1.100", "asset_type": "host"}
    await ContinuousRefreshService.emit_event(
        db=mock_db,
        change_type="ASSET_ADDED",
        asset_id=ASSET_ID,
        finding_id=None,
        previous_state=None,
        current_state=json.dumps(asset_data),
    )

    # Cache is empty initially
    BaselineStateService.clear_baselines()

    # Query will trigger rebuild
    rebuilt = BaselineStateService.get_asset_baseline(ASSET_ID)
    assert rebuilt == asset_data


@pytest.mark.asyncio
async def test_asset_drift_detection(mock_db, mock_asset) -> None:
    """Verify added, modified, and removed assets are detected as drift."""
    setup_basic_mock_db(mock_db, mock_asset, None)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf

    # Mock asset fetching: first return asset, second return same asset (modified), third return empty list
    mock_res_assets = MagicMock()
    mock_res_assets.scalars.return_value.all.side_effect = [
        [mock_asset],
        [mock_asset],
        [],
    ]

    def db_execute_side_effect(query, *args, **kwargs):
        column_desc = getattr(query, "column_descriptions", [])
        if column_desc:
            entity = column_desc[0].get("entity")
            if entity == Workflow:
                return mock_res
            elif entity == Asset:
                return mock_res_assets
            elif entity == Finding:
                m_res = MagicMock()
                m_res.scalars.return_value.all.return_value = []
                return m_res

        q_str = str(query).lower()
        if "workflow" in q_str:
            return mock_res
        elif "finding" in q_str:
            m_res = MagicMock()
            m_res.scalars.return_value.all.return_value = []
            return m_res
        elif "asset" in q_str:
            return mock_res_assets
        else:
            m_res = MagicMock()
            m_res.scalars.return_value.all.return_value = []
            return m_res

    mock_db.execute = AsyncMock(side_effect=db_execute_side_effect)

    # 1. First refresh -> ASSET_ADDED
    with patch(
        "src.services.asset_risk_snapshot_service.AssetRiskSnapshotService.get_snapshot",
        return_value={"risk_score": 50.0},
    ), patch(
        "src.services.governance_service.GovernanceService.evaluate_asset_governance",
        return_value=GovernanceStatus.COMPLIANT,
    ):
        await ContinuousRefreshService.refresh_all(mock_db)
        events = ContinuousRefreshService.get_all_events()
        assert len(events) == 1
        assert events[0].change_type == "ASSET_ADDED"

    # 2. Modify asset and refresh -> ASSET_MODIFIED
    mock_asset.host = "modified.com"
    with patch(
        "src.services.asset_risk_snapshot_service.AssetRiskSnapshotService.get_snapshot",
        return_value={"risk_score": 50.0},
    ), patch(
        "src.services.governance_service.GovernanceService.evaluate_asset_governance",
        return_value=GovernanceStatus.COMPLIANT,
    ):
        await ContinuousRefreshService.refresh_all(mock_db)
        events = ContinuousRefreshService.get_all_events()
        assert len(events) == 2
        assert events[1].change_type == "ASSET_MODIFIED"

    # 3. Remove asset and refresh -> ASSET_REMOVED
    with patch(
        "src.services.asset_risk_snapshot_service.AssetRiskSnapshotService.get_snapshot",
        return_value={"risk_score": 50.0},
    ), patch(
        "src.services.governance_service.GovernanceService.evaluate_asset_governance",
        return_value=GovernanceStatus.COMPLIANT,
    ):
        await ContinuousRefreshService.refresh_all(mock_db)
        events = ContinuousRefreshService.get_all_events()
        assert len(events) == 3
        assert events[2].change_type == "ASSET_REMOVED"


@pytest.mark.asyncio
async def test_finding_drift_detection(mock_db, mock_asset, mock_finding) -> None:
    """Verify finding drift transitions (ADDED, RESOLVED, REDISCOVERED)."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res_wf = MagicMock()
    mock_res_wf.scalar_one_or_none.return_value = mock_wf

    # Side effect for asset list
    mock_res_assets = MagicMock()
    mock_res_assets.scalars.return_value.all.return_value = [mock_asset]

    # Side effect for finding list: 1st returns [finding], 2nd returns [], 3rd returns [finding]
    mock_res_findings = MagicMock()
    mock_res_findings.scalars.return_value.all.side_effect = [
        [mock_finding],
        [],
        [mock_finding],
    ]

    def db_execute_side_effect(query, *args, **kwargs):
        column_desc = getattr(query, "column_descriptions", [])
        if column_desc:
            entity = column_desc[0].get("entity")
            if entity == Workflow:
                return mock_res_wf
            elif entity == Asset:
                return mock_res_assets
            elif entity == Finding:
                return mock_res_findings

        q_str = str(query).lower()
        if "workflow" in q_str:
            return mock_res_wf
        elif "finding" in q_str:
            return mock_res_findings
        elif "asset" in q_str:
            return mock_res_assets
        else:
            m_res = MagicMock()
            m_res.scalars.return_value.all.return_value = []
            return m_res

    mock_db.execute = AsyncMock(side_effect=db_execute_side_effect)

    # Establish baseline and add asset
    BaselineStateService.capture_asset_baseline(
        ASSET_ID, {"host": "test.com", "ip": "192.168.1.100", "asset_type": "host"}
    )

    with patch(
        "src.services.asset_risk_snapshot_service.AssetRiskSnapshotService.get_snapshot",
        return_value={"risk_score": 50.0},
    ), patch(
        "src.services.governance_service.GovernanceService.evaluate_asset_governance",
        return_value=GovernanceStatus.COMPLIANT,
    ):

        # 1. Finding Added
        await ContinuousRefreshService.refresh_all(mock_db)
        events = ContinuousRefreshService.get_all_events()
        assert any(e.change_type == "FINDING_ADDED" for e in events)

        # 2. Finding Resolved
        mock_finding.status = "resolved"
        await ContinuousRefreshService.refresh_all(mock_db)
        events = ContinuousRefreshService.get_all_events()
        assert any(e.change_type == "FINDING_RESOLVED" for e in events)

        # 3. Finding Rediscovered
        mock_finding.status = "open"
        await ContinuousRefreshService.refresh_all(mock_db)
        events = ContinuousRefreshService.get_all_events()
        assert any(e.change_type == "FINDING_REDISCOVERED" for e in events)


@pytest.mark.asyncio
async def test_risk_drift_detection(mock_db, mock_asset) -> None:
    """Verify risk changes trigger alerts when crossing 15.0 delta or 75.0 boundary."""
    setup_basic_mock_db(mock_db, mock_asset, None)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res_wf = MagicMock()
    mock_res_wf.scalar_one_or_none.return_value = mock_wf

    mock_res_assets = MagicMock()
    mock_res_assets.scalars.return_value.all.return_value = [mock_asset]

    def db_execute_side_effect(query, *args, **kwargs):
        column_desc = getattr(query, "column_descriptions", [])
        if column_desc:
            entity = column_desc[0].get("entity")
            if entity == Workflow:
                return mock_res_wf
            elif entity == Asset:
                return mock_res_assets
            elif entity == Finding:
                m_res = MagicMock()
                m_res.scalars.return_value.all.return_value = []
                return m_res

        q_str = str(query).lower()
        if "workflow" in q_str:
            return mock_res_wf
        elif "finding" in q_str:
            m_res = MagicMock()
            m_res.scalars.return_value.all.return_value = []
            return m_res
        else:
            return mock_res_assets

    mock_db.execute = AsyncMock(side_effect=db_execute_side_effect)

    BaselineStateService.capture_asset_baseline(
        ASSET_ID, {"host": "test.com", "ip": "192.168.1.100", "asset_type": "host"}
    )
    BaselineStateService.capture_risk_baseline(ASSET_ID, 50.0)

    # 1. Small change -> no event
    with patch(
        "src.services.asset_risk_snapshot_service.AssetRiskSnapshotService.get_snapshot",
        return_value={"risk_score": 60.0},
    ), patch(
        "src.services.governance_service.GovernanceService.evaluate_asset_governance",
        return_value=GovernanceStatus.COMPLIANT,
    ):
        await ContinuousRefreshService.refresh_all(mock_db)
        assert len(ContinuousRefreshService.get_all_events()) == 0

    # 2. Increase by 15.0+ -> RISK_INCREASED
    with patch(
        "src.services.asset_risk_snapshot_service.AssetRiskSnapshotService.get_snapshot",
        return_value={"risk_score": 76.0},
    ), patch(
        "src.services.governance_service.GovernanceService.evaluate_asset_governance",
        return_value=GovernanceStatus.COMPLIANT,
    ):
        await ContinuousRefreshService.refresh_all(mock_db)
        events = ContinuousRefreshService.get_all_events()
        assert len(events) == 1
        assert events[0].change_type == "RISK_INCREASED"


@pytest.mark.asyncio
async def test_compliance_drift_detection(mock_db, mock_asset) -> None:
    """Verify posture transitions are logged (COMPLIANCE_FAILED, COMPLIANCE_RESTORED)."""
    setup_basic_mock_db(mock_db, mock_asset, None)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res_wf = MagicMock()
    mock_res_wf.scalar_one_or_none.return_value = mock_wf

    mock_res_assets = MagicMock()
    mock_res_assets.scalars.return_value.all.return_value = [mock_asset]

    def db_execute_side_effect(query, *args, **kwargs):
        column_desc = getattr(query, "column_descriptions", [])
        if column_desc:
            entity = column_desc[0].get("entity")
            if entity == Workflow:
                return mock_res_wf
            elif entity == Asset:
                return mock_res_assets
            elif entity == Finding:
                m_res = MagicMock()
                m_res.scalars.return_value.all.return_value = []
                return m_res

        q_str = str(query).lower()
        if "workflow" in q_str:
            return mock_res_wf
        elif "finding" in q_str:
            m_res = MagicMock()
            m_res.scalars.return_value.all.return_value = []
            return m_res
        else:
            return mock_res_assets

    mock_db.execute = AsyncMock(side_effect=db_execute_side_effect)

    BaselineStateService.capture_asset_baseline(
        ASSET_ID, {"host": "test.com", "ip": "192.168.1.100", "asset_type": "host"}
    )
    BaselineStateService.capture_governance_baseline(ASSET_ID, "COMPLIANT")

    with patch(
        "src.services.asset_risk_snapshot_service.AssetRiskSnapshotService.get_snapshot",
        return_value={"risk_score": 50.0},
    ), patch(
        "src.services.governance_service.GovernanceService.evaluate_asset_governance",
        return_value=GovernanceStatus.NON_COMPLIANT,
    ):
        await ContinuousRefreshService.refresh_all(mock_db)
        events = ContinuousRefreshService.get_all_events()
        assert len(events) == 1
        assert events[0].change_type == "COMPLIANCE_FAILED"


@pytest.mark.asyncio
async def test_monitoring_snapshot_rebuild(mock_db) -> None:
    """Verify that cached snapshots rebuild cleanly from historical event logs."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res_wf = MagicMock()
    mock_res_wf.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res_wf)

    await ContinuousRefreshService.emit_event(
        mock_db, "ASSET_ADDED", ASSET_ID, None, None, None
    )
    await ContinuousRefreshService.emit_event(
        mock_db, "FINDING_ADDED", ASSET_ID, FINDING_ID, None, None
    )

    # Invalidate Cache
    MonitoringSnapshotService.clear_snapshots()

    snapshot = await MonitoringSnapshotService.get_snapshot(mock_db)
    assert snapshot["added_assets"] == 1
    assert snapshot["added_findings"] == 1


# --- API Endpoint Route Tests ---


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.monitoring.get_scope_by_id")
async def test_monitoring_endpoints(
    mock_get_scope,
    mock_get_user,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
    mock_asset: Asset,
    mock_db: AsyncMock,
) -> None:
    """Verify RBAC and scope filtering on monitoring endpoints."""
    mock_get_user.return_value = mock_operator
    mock_get_scope.return_value = mock_scope

    mock_db.get = AsyncMock(
        side_effect=lambda model, ident: mock_asset if model == Asset else None
    )

    # Seed an event
    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    await ContinuousRefreshService.emit_event(
        db=mock_db,
        change_type="ASSET_ADDED",
        asset_id=ASSET_ID,
        finding_id=None,
        previous_state=None,
        current_state="state",
    )

    headers = get_auth_header(OPERATOR_ID, "operator")

    # 1. Get events
    res = await client.get("/api/v1/monitoring/events", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1

    # 2. Get asset specific events
    res_asset = await client.get(
        f"/api/v1/monitoring/assets/{ASSET_ID}", headers=headers
    )
    assert res_asset.status_code == 200

    # 3. Get summary stats
    res_sum = await client.get("/api/v1/monitoring/summary", headers=headers)
    assert res_sum.status_code == 200
    assert res_sum.json()["data"]["added_assets"] == 1


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.monitoring.get_scope_by_id")
async def test_scope_violations_blocked(
    mock_get_scope,
    mock_get_user,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
    mock_asset: Asset,
    mock_db: AsyncMock,
) -> None:
    """Verify operators cannot fetch events for assets outside scope."""
    mock_get_user.return_value = mock_operator

    # Ownership mismatch
    mock_scope.owner_id = uuid.uuid4()
    mock_get_scope.return_value = mock_scope

    mock_db.get = AsyncMock(
        side_effect=lambda model, ident: mock_asset if model == Asset else None
    )

    headers = get_auth_header(OPERATOR_ID, "operator")
    res = await client.get(f"/api/v1/monitoring/assets/{ASSET_ID}", headers=headers)
    assert res.status_code == 403
