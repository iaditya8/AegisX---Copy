import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from src.core.security import create_access_token
from src.infrastructure.celery.worker import _execute_workflow_async
from src.infrastructure.database.models import (
    Asset,
    AssetPort,
    AssetService,
    Finding,
    Scope,
    User,
)
from src.services.asset_criticality_service import (
    AssetCriticality,
    AssetCriticalityService,
)
from src.services.asset_exposure_service import (
    AssetExposureService,
    ExposureClassification,
)
from src.services.asset_risk_snapshot_service import AssetRiskSnapshotService
from src.services.correlation_service import CorrelationService
from src.services.correlation_snapshot_service import CorrelationSnapshotService
from src.services.risk_factor_registry import RISK_FACTORS
from src.services.risk_scoring_service import RiskScoringService

# User and Scope IDs
ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_A_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER_B_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SCOPE_A_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
ASSET_A_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")


@pytest.fixture
def mock_admin_user() -> User:
    user = User()
    user.id = ADMIN_ID
    user.username = "admin_user"
    user.role = "admin"
    user.deleted_at = None
    return user


@pytest.fixture
def mock_operator_user() -> User:
    user = User()
    user.id = USER_A_ID
    user.username = "operator_user"
    user.role = "operator"
    user.deleted_at = None
    return user


@pytest.fixture
def mock_scope_a() -> Scope:
    s = Scope()
    s.id = SCOPE_A_ID
    s.owner_id = USER_A_ID
    s.name = "Scope A"
    s.type = "domain"
    s.definition = {"domains": ["example.com"]}
    s.deleted_at = None
    return s


@pytest.fixture
def mock_asset_a() -> Asset:
    a = Asset()
    a.id = ASSET_A_ID
    a.scope_id = SCOPE_A_ID
    a.host = "example.com"
    a.ip = "93.184.216.34"  # Public IP
    a.deleted_at = None
    return a


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


def setup_mock_db_queries(mock_db, asset, ports, services, findings):
    """Helper to mock common query paths in correlation and criticality services."""
    mock_db.get.return_value = asset
    # Ensure synchronous SQLAlchemy methods are not returned as coroutines
    mock_db.add = MagicMock()

    def db_execute_mock(q, *args, **kwargs):
        q_str = str(q).lower()
        res = MagicMock()
        if "asset_ports" in q_str:
            res.scalars().all.return_value = ports
        elif "asset_services" in q_str:
            res.scalars().all.return_value = services
        elif "findings" in q_str:
            res.scalars().all.return_value = findings
        else:
            res.scalars().all.return_value = []
        return res

    mock_db.execute.side_effect = db_execute_mock


# ==============================================================================
# 1. Correlation Service Tests (Tests 1-6)
# ==============================================================================


@pytest.mark.asyncio
async def test_correlation_generation(mock_db, mock_asset_a) -> None:
    """Requirement 1: Asset correlation generation. Verify general flow works."""
    setup_mock_db_queries(mock_db, mock_asset_a, [], [], [])
    res = await CorrelationService.correlate_asset(mock_db, ASSET_A_ID)
    assert res["asset_id"] == str(ASSET_A_ID)
    assert res["exposure"] == "EXTERNAL"


@pytest.mark.asyncio
async def test_port_aggregation(mock_db, mock_asset_a) -> None:
    """Requirement 2: Port aggregation. Verify open ports are sorted."""
    port1 = AssetPort(
        id=uuid.uuid4(), asset_id=ASSET_A_ID, port=443, protocol="tcp", state="open"
    )
    port2 = AssetPort(
        id=uuid.uuid4(), asset_id=ASSET_A_ID, port=80, protocol="tcp", state="open"
    )
    setup_mock_db_queries(mock_db, mock_asset_a, [port1, port2], [], [])

    res = await CorrelationService.correlate_asset(mock_db, ASSET_A_ID)
    assert res["ports"] == ["443/tcp", "80/tcp"]  # sorted alphabetically/numerically


@pytest.mark.asyncio
async def test_service_aggregation(mock_db, mock_asset_a) -> None:
    """Requirement 3: Service aggregation. Verify service names are sorted."""
    port = AssetPort(
        id=uuid.uuid4(), asset_id=ASSET_A_ID, port=80, protocol="tcp", state="open"
    )
    svc1 = AssetService(id=uuid.uuid4(), asset_port_id=port.id, service_name="http")
    svc2 = AssetService(
        id=uuid.uuid4(), asset_port_id=port.id, service_name="http-proxy"
    )
    setup_mock_db_queries(mock_db, mock_asset_a, [port], [svc1, svc2], [])

    res = await CorrelationService.correlate_asset(mock_db, ASSET_A_ID)
    assert res["services"] == ["http", "http-proxy"]


@pytest.mark.asyncio
async def test_technology_aggregation(mock_db, mock_asset_a) -> None:
    """Requirement 4: Tech aggregation. Verify tech stack aggregates products."""
    port = AssetPort(
        id=uuid.uuid4(), asset_id=ASSET_A_ID, port=80, protocol="tcp", state="open"
    )
    svc = AssetService(
        id=uuid.uuid4(), asset_port_id=port.id, service_name="http", product="nginx"
    )
    setup_mock_db_queries(mock_db, mock_asset_a, [port], [svc], [])

    res = await CorrelationService.correlate_asset(mock_db, ASSET_A_ID)
    assert "nginx" in res["technologies"]


@pytest.mark.asyncio
async def test_product_aggregation(mock_db, mock_asset_a) -> None:
    """Requirement 5: Product aggregation. Verify products aggregates products."""
    port = AssetPort(
        id=uuid.uuid4(), asset_id=ASSET_A_ID, port=80, protocol="tcp", state="open"
    )
    svc = AssetService(
        id=uuid.uuid4(), asset_port_id=port.id, service_name="http", product="apache"
    )
    setup_mock_db_queries(mock_db, mock_asset_a, [port], [svc], [])

    res = await CorrelationService.correlate_asset(mock_db, ASSET_A_ID)
    assert "apache" in res["products"]


@pytest.mark.asyncio
async def test_finding_aggregation(mock_db, mock_asset_a) -> None:
    """Requirement 6: Finding aggregation. Verify counts exclude closed."""
    f1 = Finding(
        id=uuid.uuid4(),
        asset_id=ASSET_A_ID,
        severity="high",
        status="open",
        metadata_json={},
    )
    f2 = Finding(
        id=uuid.uuid4(),
        asset_id=ASSET_A_ID,
        severity="critical",
        status="acknowledged",
        metadata_json={},
    )
    f3 = Finding(
        id=uuid.uuid4(),
        asset_id=ASSET_A_ID,
        severity="medium",
        status="open",
        metadata_json={"closed_by_scan": True},
    )
    setup_mock_db_queries(mock_db, mock_asset_a, [], [], [f1, f2, f3])

    res = await CorrelationService.correlate_asset(mock_db, ASSET_A_ID)
    # f3 is closed_by_scan, so it should not be counted
    assert res["finding_counts"]["high"] == 1
    assert res["finding_counts"]["critical"] == 1
    assert res["finding_counts"]["medium"] == 0


# ==============================================================================
# 2. Asset Exposure Classification Tests (Tests 7-9)
# ==============================================================================


def test_external_classification() -> None:
    """Requirement 7: External asset classification. Public IP or internet host."""
    asset = Asset(ip="8.8.8.8", host="google.com")
    assert AssetExposureService.classify(asset) == ExposureClassification.EXTERNAL

    asset_only_host = Asset(ip=None, host="internet.example.com")
    assert (
        AssetExposureService.classify(asset_only_host)
        == ExposureClassification.EXTERNAL
    )


def test_internal_classification() -> None:
    """Requirement 8: Internal asset classification. Private RFC1918/local."""
    asset1 = Asset(ip="192.168.1.5", host="myhost.local")
    assert AssetExposureService.classify(asset1) == ExposureClassification.INTERNAL

    asset2 = Asset(ip="10.0.0.1", host="server.internal")
    assert AssetExposureService.classify(asset2) == ExposureClassification.INTERNAL


def test_unknown_classification() -> None:
    """Requirement 9: Unknown classification. Insufficient info."""
    asset = Asset(ip=None, host=None)
    assert AssetExposureService.classify(asset) == ExposureClassification.UNKNOWN


# ==============================================================================
# 3. Asset Criticality Engine Tests (Tests 10-11)
# ==============================================================================


@pytest.mark.asyncio
async def test_criticality_calculation(mock_db, mock_asset_a) -> None:
    """Requirement 10: Asset criticality calculation."""
    port = AssetPort(
        id=uuid.uuid4(), asset_id=ASSET_A_ID, port=80, protocol="tcp", state="open"
    )
    svc = AssetService(
        id=uuid.uuid4(), asset_port_id=port.id, service_name="http", product="nginx"
    )
    f = Finding(
        id=uuid.uuid4(),
        asset_id=ASSET_A_ID,
        severity="critical",
        status="open",
        metadata_json={},
    )

    setup_mock_db_queries(mock_db, mock_asset_a, [port], [svc], [f])

    res = await AssetCriticalityService.calculate_asset_criticality(mock_db, ASSET_A_ID)
    assert "criticality" in res
    assert "score" in res
    # 30 (external) + 25 (critical finding) + 5 (1 service) + 4 (1 tech) = 64
    assert res["score"] == 64
    assert len(res["reasons"]) > 0


def test_criticality_level_mapping() -> None:
    """Requirement 11: Criticality level mapping."""
    assert AssetCriticality.LOW == "LOW"
    assert AssetCriticality.CRITICAL == "CRITICAL"


# ==============================================================================
# 4. Risk Scoring Engine & Explanations Tests (Tests 12-18)
# ==============================================================================


def test_risk_score_calculation_and_explanation() -> None:
    """Requirements 12, 13, 14: Score, level, explanation generation."""
    snapshot = {
        "asset_id": str(ASSET_A_ID),
        "risk_factors": ["internet_exposed", "critical_finding_present"],
    }
    res = RiskScoringService.calculate_risk(snapshot)
    # Weight: internet_exposed (20) + critical_finding_present (25) = 45
    assert res["risk_score"] == 45
    assert res["risk_level"] == "MEDIUM"
    assert len(res["explanations"]) == 2
    assert res["explanations"][0]["factor"] == "internet_exposed"
    assert res["explanations"][0]["impact"] == 20


def test_registry_driven_scoring() -> None:
    """Requirement 15: Registry-driven scoring. Weights must match registry."""
    snapshot = {"risk_factors": ["high_finding_count"]}
    res = RiskScoringService.calculate_risk(snapshot)
    assert res["risk_score"] == RISK_FACTORS["high_finding_count"]


def test_multiple_factor_accumulation() -> None:
    """Requirement 16: Multiple factor accumulation."""
    snapshot = {
        "risk_factors": ["internet_exposed", "multiple_open_ports", "multiple_services"]
    }
    res = RiskScoringService.calculate_risk(snapshot)
    # 20 + 10 + 10 = 40
    assert res["risk_score"] == 40


def test_critical_finding_impact() -> None:
    """Requirement 17: Critical finding impact."""
    snapshot = {"risk_factors": ["critical_finding_present"]}
    res = RiskScoringService.calculate_risk(snapshot)
    assert res["risk_score"] == 25


def test_score_clamping() -> None:
    """Requirement 18: Score clamping (0 <= score <= 100)."""
    # Over 100 sum
    snapshot_high = {
        "risk_factors": [
            "internet_exposed",
            "critical_finding_present",
            "high_finding_count",
            "multiple_open_ports",
            "multiple_services",
            "high_attack_surface",
        ]
    }
    res_high = RiskScoringService.calculate_risk(snapshot_high)
    assert res_high["risk_score"] == 100  # clamped at 100

    # Negative/empty sum
    snapshot_empty = {"risk_factors": []}
    res_empty = RiskScoringService.calculate_risk(snapshot_empty)
    assert res_empty["risk_score"] == 0  # clamped at 0


# ==============================================================================
# 5. Snapshots & Updates Tests (Tests 19-21)
# ==============================================================================


@pytest.mark.asyncio
async def test_correlation_snapshot_generation(mock_db, mock_asset_a) -> None:
    """Requirement 19: Correlation snapshot generation."""
    setup_mock_db_queries(mock_db, mock_asset_a, [], [], [])
    snapshot = await CorrelationSnapshotService.update_snapshot(mock_db, ASSET_A_ID)
    assert snapshot["asset_id"] == str(ASSET_A_ID)
    assert CorrelationSnapshotService.get_snapshot(ASSET_A_ID)["exposure"] == "EXTERNAL"


@pytest.mark.asyncio
async def test_risk_snapshot_generation(mock_db, mock_asset_a) -> None:
    """Requirement 20: Risk snapshot generation."""
    # Seed correlation cache
    setup_mock_db_queries(mock_db, mock_asset_a, [], [], [])
    await CorrelationSnapshotService.update_snapshot(mock_db, ASSET_A_ID)

    # Re-mock db queries for risk snapshot generation
    setup_mock_db_queries(mock_db, mock_asset_a, [], [], [])
    risk_snapshot = await AssetRiskSnapshotService.update_snapshot(mock_db, ASSET_A_ID)
    assert risk_snapshot["asset_id"] == str(ASSET_A_ID)
    assert risk_snapshot["risk_level"] == "LOW"
    # Internet exposed risk factor should evaluate to 20
    assert AssetRiskSnapshotService.get_snapshot(ASSET_A_ID)["risk_score"] == 20


@pytest.mark.asyncio
async def test_snapshot_refresh_after_finding_update(mock_db, mock_asset_a) -> None:
    """Requirement 21: Snapshot refresh after finding update."""
    # Step 1: Generate initial snapshot with no findings (score = 20 from public IP)
    setup_mock_db_queries(mock_db, mock_asset_a, [], [], [])
    await CorrelationSnapshotService.update_snapshot(mock_db, ASSET_A_ID)
    await AssetRiskSnapshotService.update_snapshot(mock_db, ASSET_A_ID)
    assert AssetRiskSnapshotService.get_snapshot(ASSET_A_ID)["risk_score"] == 20

    # Step 2: Seed new findings in DB and update snapshots
    f = Finding(
        id=uuid.uuid4(),
        asset_id=ASSET_A_ID,
        severity="critical",
        status="open",
        metadata_json={},
    )
    setup_mock_db_queries(mock_db, mock_asset_a, [], [], [f])
    await CorrelationSnapshotService.update_snapshot(mock_db, ASSET_A_ID)

    setup_mock_db_queries(mock_db, mock_asset_a, [], [], [f])
    await AssetRiskSnapshotService.update_snapshot(mock_db, ASSET_A_ID)

    # Score should now reflect critical finding (25) + external (20) = 45
    assert AssetRiskSnapshotService.get_snapshot(ASSET_A_ID)["risk_score"] == 45


# ==============================================================================
# 6. Workflow Integration Tests (Tests 22-23)
# ==============================================================================


@pytest.mark.asyncio
@patch("src.plugins.host.PluginHost.run_plugin")
async def test_correlation_and_risk_refresh_after_scan(
    mock_run_plugin, mock_db, mock_asset_a
) -> None:
    """Requirements 22, 23: Correlation/risk refresh after scan workflow."""
    mock_run_plugin.return_value = {"raw_output": "test output"}
    mock_db.add = MagicMock()

    # Setup database mocks for worker execution
    from src.infrastructure.database.models import ScanRun, Workflow

    wf = Workflow(
        id=uuid.uuid4(),
        owner_id=USER_A_ID,
        definition={"steps": [{"type": "discovery", "tool": "subfinder"}]},
    )
    scan_run = ScanRun(
        id=uuid.uuid4(), workflow_id=wf.id, scope_id=SCOPE_A_ID, status="pending"
    )

    # Mocks for DB operations in worker loop
    mock_db.get.side_effect = lambda model, obj_id: {
        Workflow: wf,
        ScanRun: scan_run,
        Scope: Scope(id=SCOPE_A_ID, owner_id=USER_A_ID, deleted_at=None),
        Asset: mock_asset_a,
    }.get(model)

    # 1. Plugin lookup query
    mock_plugin_res = MagicMock()
    mock_plugin_res.scalar_one_or_none.return_value = MagicMock(
        name="subfinder",
        state="approved",
        manifest={"capabilities": ["discovery"], "entry_point": "main", "timeout": 30},
    )

    # 2. Asset query inside worker snapshot refresh block
    mock_assets_res = MagicMock()
    mock_assets_res.scalars().all.return_value = [mock_asset_a]

    with patch(
        "src.services.discovery_normalization_service.DiscoveryNormalizationService.normalize"
    ) as mock_norm, patch(
        "src.services.asset_service.process_discovered_assets"
    ) as mock_proc:
        mock_norm.return_value = []
        mock_proc.return_value = []

        mock_db_res = MagicMock()
        mock_db_res.scalars().all.return_value = []

        # Intercept executes dynamically
        def dynamic_execute(q, *args, **kwargs):
            q_str = str(q).lower()
            res = MagicMock()
            if "plugins" in q_str:
                return mock_plugin_res
            elif "assets" in q_str:
                res.scalars().all.return_value = [mock_asset_a]
            elif "asset_ports" in q_str:
                res.scalars().all.return_value = []
            elif "asset_services" in q_str:
                res.scalars().all.return_value = []
            elif "findings" in q_str:
                res.scalars().all.return_value = []
            else:
                res.scalars().all.return_value = []
            return res

        mock_db.execute.side_effect = dynamic_execute

        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_db
        with patch(
            "src.infrastructure.celery.worker.AsyncSessionLocal", mock_session_factory
        ):
            # Call worker
            await _execute_workflow_async(wf.id, scan_run.id, SCOPE_A_ID)

        # Verify snapshots were cached
        assert CorrelationSnapshotService.get_snapshot(mock_asset_a.id) is not None
        assert AssetRiskSnapshotService.get_snapshot(mock_asset_a.id) is not None


# ==============================================================================
# 7. API Integration Tests (Tests 24-25)
# ==============================================================================


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.correlations.get_asset_by_id")
@patch("src.api.v1.routers.correlations.get_scope_by_id")
async def test_get_correlation_endpoint(
    mock_get_scope: MagicMock,
    mock_get_asset: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_operator_user: User,
    mock_scope_a: Scope,
    mock_asset_a: Asset,
    mock_db: AsyncMock,
) -> None:
    """Requirement 24: GET correlation endpoint."""
    mock_get_user.return_value = mock_operator_user
    mock_get_asset.return_value = mock_asset_a
    mock_get_scope.return_value = mock_scope_a
    setup_mock_db_queries(mock_db, mock_asset_a, [], [], [])

    # Seed snapshot caches to avoid real generation triggers
    CorrelationSnapshotService._snapshots[ASSET_A_ID] = {
        "asset_id": str(ASSET_A_ID),
        "exposure": "EXTERNAL",
        "ports": [],
        "services": [],
        "products": [],
        "finding_counts": {},
        "risk_factors": [],
    }

    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.get(
        f"/api/v1/assets/{ASSET_A_ID}/correlation", headers=headers
    )

    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert res["data"]["asset_id"] == str(ASSET_A_ID)


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.correlations.get_asset_by_id")
@patch("src.api.v1.routers.correlations.get_scope_by_id")
async def test_get_risk_endpoint(
    mock_get_scope: MagicMock,
    mock_get_asset: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_operator_user: User,
    mock_scope_a: Scope,
    mock_asset_a: Asset,
    mock_db: AsyncMock,
) -> None:
    """Requirement 25: GET risk endpoint."""
    mock_get_user.return_value = mock_operator_user
    mock_get_asset.return_value = mock_asset_a
    mock_get_scope.return_value = mock_scope_a
    setup_mock_db_queries(mock_db, mock_asset_a, [], [], [])

    # Seed snapshot caches to avoid real generation triggers
    AssetRiskSnapshotService._snapshots[ASSET_A_ID] = {
        "asset_id": str(ASSET_A_ID),
        "criticality": "LOW",
        "risk_score": 20,
        "risk_level": "LOW",
        "exposure": "EXTERNAL",
        "finding_counts": {},
        "risk_factors": [],
        "explanations": [],
    }

    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.get(f"/api/v1/assets/{ASSET_A_ID}/risk", headers=headers)

    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert res["data"]["risk_level"] == "LOW"


# ==============================================================================
# 8. Stability & Resilience Tests (Tests 26-28)
# ==============================================================================


@pytest.mark.asyncio
async def test_missing_asset_handling(mock_db) -> None:
    """Requirement 26: Missing asset handling. Graceful defaults."""
    missing_id = uuid.uuid4()
    mock_db.get.return_value = None
    mock_db.add = MagicMock()

    # Correlation Service
    corr_res = await CorrelationService.correlate_asset(mock_db, missing_id)
    assert corr_res["asset_id"] == str(missing_id)
    assert corr_res["exposure"] == "UNKNOWN"
    assert corr_res["ports"] == []

    # Criticality Service
    crit_res = await AssetCriticalityService.calculate_asset_criticality(
        mock_db, missing_id
    )
    assert crit_res["criticality"] == AssetCriticality.LOW
    assert crit_res["score"] == 0


@pytest.mark.asyncio
async def test_empty_asset_handling(mock_db, mock_asset_a) -> None:
    """Requirement 27: Empty asset handling. No open ports or findings."""
    setup_mock_db_queries(mock_db, mock_asset_a, [], [], [])

    # Correlation Service
    corr_res = await CorrelationService.correlate_asset(mock_db, ASSET_A_ID)
    assert corr_res["asset_id"] == str(ASSET_A_ID)
    assert corr_res["exposure"] == "EXTERNAL"
    assert corr_res["ports"] == []
    assert corr_res["risk_factors"] == ["internet_exposed"]


@pytest.mark.asyncio
@patch("src.plugins.host.PluginHost.run_plugin")
async def test_worker_resilience(mock_run_plugin, mock_db, mock_asset_a) -> None:
    """Requirement 28: Worker resilience. Verify snapshot errors do not crash."""
    mock_run_plugin.return_value = {"raw_output": "test output"}
    mock_db.add = MagicMock()

    # Setup database mocks for worker execution
    from src.infrastructure.database.models import ScanRun, Workflow

    wf = Workflow(
        id=uuid.uuid4(),
        owner_id=USER_A_ID,
        definition={"steps": [{"type": "discovery", "tool": "subfinder"}]},
    )
    scan_run = ScanRun(
        id=uuid.uuid4(), workflow_id=wf.id, scope_id=SCOPE_A_ID, status="pending"
    )

    mock_db.get.side_effect = lambda model, obj_id: {
        Workflow: wf,
        ScanRun: scan_run,
        Scope: Scope(id=SCOPE_A_ID, owner_id=USER_A_ID, deleted_at=None),
        Asset: mock_asset_a,
    }.get(model)

    mock_plugin_res = MagicMock()
    mock_plugin_res.scalar_one_or_none.return_value = MagicMock(
        name="subfinder",
        state="approved",
        manifest={"capabilities": ["discovery"], "entry_point": "main", "timeout": 30},
    )

    mock_assets_res = MagicMock()
    mock_assets_res.scalars().all.return_value = [mock_asset_a]

    # Setup db side effect queries
    mock_db.execute.side_effect = [
        mock_plugin_res,  # Plugin lookup
        mock_assets_res,  # Asset query in worker
    ]

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db

    # Mock AssetIntelligenceService to crash during update
    with patch(
        "src.services.asset_intelligence_service.AssetIntelligenceService.update_asset_snapshot",
        side_effect=Exception("Database down"),
    ), patch(
        "src.services.discovery_normalization_service.DiscoveryNormalizationService.normalize",
        return_value=[],
    ), patch(
        "src.services.asset_service.process_discovered_assets", return_value=[]
    ), patch(
        "src.infrastructure.celery.worker.AsyncSessionLocal", mock_session_factory
    ):

        # Call worker - should complete without throwing exceptions
        await _execute_workflow_async(wf.id, scan_run.id, SCOPE_A_ID)

        # ScanRun status should be completed because exception is caught internally
        assert scan_run.status == "completed"


# ==============================================================================
# 9. Sprint 9 Hardening Improvements Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_criticality_registry_usage(mock_db, mock_asset_a) -> None:
    """Verify AssetCriticalityService dynamically consumes registry values."""
    from src.services.criticality_factor_registry import CRITICALITY_FACTORS

    # Temporary override the registry weight
    with patch.dict(CRITICALITY_FACTORS, {"external_asset": 55}):
        setup_mock_db_queries(mock_db, mock_asset_a, [], [], [])
        res = await AssetCriticalityService.calculate_asset_criticality(
            mock_db, ASSET_A_ID
        )
        # Score should reflect the patched external weight (55)
        assert res["score"] == 55


def test_exposure_extension_point() -> None:
    """Verify existing classifications and extension point are intact."""
    from src.services.asset_exposure_service import SUPPORTED_EXPOSURE_CLASSES

    assert "INTERNAL" in SUPPORTED_EXPOSURE_CLASSES
    assert "EXTERNAL" in SUPPORTED_EXPOSURE_CLASSES
    assert "UNKNOWN" in SUPPORTED_EXPOSURE_CLASSES

    # Test private helpers
    asset_ext = Asset(ip="8.8.8.8", host="google.com")
    asset_int = Asset(ip="10.0.0.1", host="server.local")

    assert AssetExposureService._is_public_asset(asset_ext) is True
    assert AssetExposureService._is_public_asset(asset_int) is False

    assert AssetExposureService._is_internal_asset(asset_ext) is False
    assert AssetExposureService._is_internal_asset(asset_int) is True


@pytest.mark.asyncio
async def test_risk_criticality_independence(mock_db, mock_asset_a) -> None:
    """Verify High criticality asset does not automatically imply high risk."""
    # Mock a critical asset with no vulnerabilities (no findings)
    port = AssetPort(
        id=uuid.uuid4(), asset_id=ASSET_A_ID, port=80, protocol="tcp", state="open"
    )
    svc = AssetService(
        id=uuid.uuid4(), asset_port_id=port.id, service_name="http", product="nginx"
    )
    # Empty findings list
    setup_mock_db_queries(mock_db, mock_asset_a, [port], [svc], [])

    # Calculate criticality
    crit_res = await AssetCriticalityService.calculate_asset_criticality(
        mock_db, ASSET_A_ID
    )
    # Calculate risk snapshot
    await CorrelationSnapshotService.update_snapshot(mock_db, ASSET_A_ID)
    risk_snapshot = await AssetRiskSnapshotService.update_snapshot(mock_db, ASSET_A_ID)

    # 30 (external) + 5 (1 service) + 4 (1 tech) = 39 (MEDIUM criticality)
    assert crit_res["score"] == 39
    assert crit_res["criticality"] == AssetCriticality.MEDIUM

    # Risk score should reflect only 'internet_exposed' weight (20)
    assert risk_snapshot["risk_score"] == 20
    assert risk_snapshot["risk_level"] == "LOW"  # 20 <= 24 is LOW
