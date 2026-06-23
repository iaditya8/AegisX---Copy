import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from src.core.security import create_access_token
from src.infrastructure.database.models import (
    Asset,
    Finding,
    FindingHistory,
    Scope,
    User,
)
from src.services.asset_report_service import AssetReportService
from src.services.asset_risk_snapshot_service import AssetRiskSnapshotService
from src.services.correlation_snapshot_service import CorrelationSnapshotService
from src.services.dashboard_service import DashboardService
from src.services.dashboard_trend_service import DashboardTrendService
from src.services.executive_report_service import ExecutiveReportService
from src.services.export_service import ExportService
from src.services.exposure_report_service import ExposureReportService
from src.services.finding_report_service import FindingReportService
from src.services.risk_history_service import RiskHistoryService
from src.services.risk_report_service import RiskReportService

# Test IDs
ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_A_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER_B_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SCOPE_A_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
ASSET_A_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
ASSET_B_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")


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
def mock_reader_user() -> User:
    user = User()
    user.id = USER_B_ID
    user.username = "reader_user"
    user.role = "reader"
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
    a.ip = "93.184.216.34"
    a.asset_type = "domain"
    a.deleted_at = None
    return a


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


def setup_mock_db_queries(
    mock_db,
    assets=None,
    ports=None,
    services=None,
    findings=None,
    histories=None,
    scope=None,
):
    """Utility to setup db.execute mock returns for reporting queries."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    if assets is None:
        assets = []
    if ports is None:
        ports = []
    if services is None:
        services = []
    if findings is None:
        findings = []
    if histories is None:
        histories = []

    def db_execute_mock(q, *args, **kwargs):
        q_str = str(q).lower()
        res = MagicMock()

        # Handle COUNT queries
        if "count" in q_str:
            scalar_res = MagicMock()
            if "asset_ports" in q_str:
                scalar_res.scalar.return_value = len(ports)
            elif "asset_services" in q_str:
                scalar_res.scalar.return_value = len(services)
            elif "findings" in q_str:
                scalar_res.scalar.return_value = len(findings)
            else:
                scalar_res.scalar.return_value = len(assets)
            return scalar_res

        # Handle SELECT queries
        if "asset_ports" in q_str:
            res.scalars().all.return_value = ports
        elif "asset_services" in q_str:
            res.all.return_value = [(s, 80) for s in services]
        elif "finding_history" in q_str:
            res.all.return_value = histories
        elif "findings" in q_str:
            res.scalars().all.return_value = findings
        elif "assets" in q_str:
            res.scalars().all.return_value = assets
        elif "scopes" in q_str:
            res.scalar_one_or_none.return_value = scope if scope else mock_scope_a
        elif "workflows" in q_str:
            wf = MagicMock()
            wf.id = uuid.uuid4()
            res.scalar_one_or_none.return_value = wf
        else:
            res.scalars().all.return_value = []
        return res

    mock_db.execute = AsyncMock(side_effect=db_execute_mock)

    async def get_mock(model_cls, pk):
        if pk is None:
            return None
        if model_cls.__name__ == "Asset":
            for a in assets:
                if str(a.id) == str(pk):
                    return a
            if str(pk) == str(ASSET_A_ID):
                # Return a default asset if queried
                a = Asset()
                a.id = ASSET_A_ID
                a.scope_id = SCOPE_A_ID
                a.host = "example.com"
                a.ip = "93.184.216.34"
                a.asset_type = "domain"
                a.deleted_at = None
                return a
            return None
        if model_cls.__name__ == "Scope":
            if scope:
                return scope
            s = Scope()
            s.id = SCOPE_A_ID
            s.owner_id = USER_A_ID
            s.deleted_at = None
            return s
        return None

    mock_db.get = AsyncMock(side_effect=get_mock)


# ==============================================================================
# 1. CORE SERVICE TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_dashboard_summary_generation(mock_db, mock_asset_a) -> None:
    """Test Dashboard summary aggregation logic."""
    setup_mock_db_queries(
        mock_db, assets=[mock_asset_a], ports=[], services=[], findings=[]
    )
    DashboardService.clear_cache()

    # Seed snapshot
    AssetRiskSnapshotService._snapshots[ASSET_A_ID] = {
        "asset_id": str(ASSET_A_ID),
        "exposure": "EXTERNAL",
        "risk_score": 55,
        "risk_level": "HIGH",
    }

    stats = await DashboardService.get_dashboard_summary(mock_db, bypass_cache=True)
    assert stats["asset_count"] == 1
    assert stats["internet_exposed_assets"] == 1
    assert stats["risk"]["high"] == 1


@pytest.mark.asyncio
async def test_dashboard_trend_generation(mock_db) -> None:
    """Test Dashboard trend time-series calculation."""
    # Seed Risk History
    RiskHistoryService.clear_history()
    await RiskHistoryService.record_history(
        mock_db, ASSET_A_ID, 20, "LOW", "LOW", workflow_id=uuid.uuid4()
    )
    await RiskHistoryService.record_history(
        mock_db, ASSET_A_ID, 60, "HIGH", "LOW", workflow_id=uuid.uuid4()
    )

    # Seed Finding History
    f = Finding()
    f.severity = "critical"
    fh = FindingHistory()
    fh.created_at = datetime.now(timezone.utc)
    fh.change_type = "create"

    setup_mock_db_queries(mock_db, histories=[(fh, "critical")])

    trends = await DashboardTrendService.generate_trends(mock_db)
    assert len(trends["risk_trend"]) == 2
    assert trends["risk_trend"][-1]["value"] == 60.0
    assert len(trends["finding_trend"]) == 1
    assert trends["finding_trend"][0]["value"] == 1.0


@pytest.mark.asyncio
async def test_executive_report_generation(mock_db, mock_asset_a) -> None:
    """Test Executive Report compiling logic."""
    setup_mock_db_queries(mock_db, assets=[mock_asset_a])
    ExecutiveReportService.clear_cache()

    # Seed Dashboard and Snapshots
    DashboardService._cache = {
        "asset_count": 1,
        "internet_exposed_assets": 1,
        "open_ports": 0,
        "services": 0,
        "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
        "risk": {"critical": 0, "high": 1, "medium": 0, "low": 0},
    }
    AssetRiskSnapshotService._snapshots[ASSET_A_ID] = {
        "asset_id": str(ASSET_A_ID),
        "exposure": "EXTERNAL",
        "risk_score": 60,
        "risk_level": "HIGH",
        "criticality": "LOW",
    }

    report = await ExecutiveReportService.get_executive_report(
        mock_db, bypass_cache=True
    )
    assert report["summary"]["asset_count"] == 1
    assert len(report["top_risky_assets"]) == 1
    assert report["top_risky_assets"][0]["risk_score"] == 60


@pytest.mark.asyncio
async def test_asset_report_generation(mock_db, mock_asset_a) -> None:
    """Test Asset report dynamic data compilation."""
    setup_mock_db_queries(mock_db, assets=[mock_asset_a])

    # Seed snapshots
    CorrelationSnapshotService._snapshots[ASSET_A_ID] = {
        "asset_id": str(ASSET_A_ID),
        "exposure": "EXTERNAL",
        "ports": [80],
        "services": ["http"],
        "technologies": ["nginx"],
    }
    AssetRiskSnapshotService._snapshots[ASSET_A_ID] = {
        "asset_id": str(ASSET_A_ID),
        "criticality": "LOW",
        "risk_score": 40,
        "risk_level": "MEDIUM",
        "explanations": [],
    }

    report = await AssetReportService.generate_asset_report(mock_db, ASSET_A_ID)
    assert report["asset"]["id"] == str(ASSET_A_ID)
    assert report["exposure"]["classification"] == "EXTERNAL"
    assert report["risk"]["risk_score"] == 40
    assert "nginx" in report["technologies"]


@pytest.mark.asyncio
async def test_finding_report_generation(mock_db, mock_asset_a) -> None:
    """Test Finding report filtering mechanism."""
    f = Finding()
    f.id = uuid.uuid4()
    f.asset_id = ASSET_A_ID
    f.title = "XSS"
    f.severity = "high"
    f.status = "open"
    f.template_id = "xss-template"

    setup_mock_db_queries(mock_db, assets=[mock_asset_a], findings=[f])

    report = await FindingReportService.generate_finding_report(
        mock_db, severity="high", status="open", template="xss-template"
    )
    assert report["total_count"] == 1
    assert report["findings"][0]["title"] == "XSS"


@pytest.mark.asyncio
async def test_risk_report_generation(mock_db, mock_asset_a) -> None:
    """Test Risk report mapping and risk history loading."""
    setup_mock_db_queries(mock_db, assets=[mock_asset_a])
    AssetRiskSnapshotService._snapshots[ASSET_A_ID] = {
        "asset_id": str(ASSET_A_ID),
        "exposure": "EXTERNAL",
        "risk_score": 80,
        "risk_level": "CRITICAL",
        "criticality": "HIGH",
    }
    RiskHistoryService.clear_history()
    await RiskHistoryService.record_history(
        mock_db, ASSET_A_ID, 80, "CRITICAL", "HIGH", workflow_id=uuid.uuid4()
    )

    report = await RiskReportService.generate_risk_report(mock_db)
    assert report["risk_distribution"]["critical"] == 1
    assert len(report["critical_assets"]) == 1
    assert len(report["risk_history"]) == 1


@pytest.mark.asyncio
async def test_exposure_report_generation(mock_db, mock_asset_a) -> None:
    """Test Exposure report category distribution classification."""
    setup_mock_db_queries(mock_db, assets=[mock_asset_a])
    CorrelationSnapshotService._snapshots[ASSET_A_ID] = {
        "asset_id": str(ASSET_A_ID),
        "exposure": "EXTERNAL",
        "ports": [],
        "services": [],
        "technologies": [],
    }

    report = await ExposureReportService.generate_exposure_report(mock_db)
    assert report["internet_exposed_count"] == 1
    assert len(report["external_assets"]) == 1


# ==============================================================================
# 2. EXPORT SERVICE TESTS
# ==============================================================================


def test_export_executive_json() -> None:
    """Test JSON export formatting for Executive Report."""
    dummy_report = {"summary": {"asset_count": 5}, "top_risky_assets": []}
    result = ExportService.export_executive_report_json(dummy_report)
    parsed = json.loads(result)
    assert parsed["data"]["summary"]["asset_count"] == 5


def test_export_asset_json() -> None:
    """Test JSON export formatting for Asset Report."""
    dummy_report = {"asset": {"id": "123"}, "exposure": {}, "risk": {}}
    result = ExportService.export_asset_report_json(dummy_report)
    parsed = json.loads(result)
    assert parsed["data"]["asset"]["id"] == "123"


def test_export_executive_csv() -> None:
    """Test CSV export and header integrity for Executive Report."""
    dummy_report = {
        "summary": {
            "asset_count": 10,
            "internet_exposed_assets": 2,
            "open_ports": 3,
            "services": 1,
        },
        "risk_distribution": {"critical": 1},
        "exposure_distribution": {"EXTERNAL": 2},
        "top_risky_assets": [
            {
                "id": "asset-1",
                "host": "test.com",
                "ip": "1.1.1.1",
                "asset_type": "host",
                "risk_score": 90,
                "risk_level": "CRITICAL",
                "criticality": "HIGH",
            }
        ],
        "critical_findings": [],
    }

    csv_data = ExportService.export_executive_report_csv(dummy_report)
    assert "Section,Metric,Value" in csv_data
    assert "Asset Count,10" in csv_data
    assert "Top Risky Assets - ID" in csv_data
    assert "asset-1,test.com" in csv_data


def test_export_asset_csv() -> None:
    """Test CSV export structure validation for Asset Report."""
    dummy_report = {
        "asset": {"id": "asset-1", "host": "test.com", "ip": "1.1.1.1"},
        "exposure": {"classification": "EXTERNAL", "risk_factors": ["factor1"]},
        "risk": {"risk_score": 75, "risk_level": "CRITICAL", "criticality": "HIGH"},
        "ports": [],
        "services": [],
        "technologies": ["nginx"],
        "findings": [],
    }

    csv_data = ExportService.export_asset_report_csv(dummy_report)
    assert "Asset Details,ID,asset-1" in csv_data
    assert "Exposure,Classification,EXTERNAL" in csv_data
    assert "Technologies,nginx" in csv_data


# ==============================================================================
# 3. API ROUTER & RBAC TESTS
# ==============================================================================


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_executive_report_api(
    mock_get_user, client: AsyncClient, mock_db, mock_reader_user
) -> None:
    """Test GET /api/v1/reports/executive endpoint with Reader access."""
    mock_get_user.return_value = mock_reader_user
    setup_mock_db_queries(mock_db)

    # Seed cache
    ExecutiveReportService._cache = {
        "summary": {"asset_count": 0},
        "top_risky_assets": [],
        "critical_findings": [],
        "risk_distribution": {},
        "exposure_distribution": {},
    }

    headers = get_auth_header(USER_B_ID, "reader")
    response = await client.get("/api/v1/reports/executive", headers=headers)
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_asset_report_api(
    mock_get_user,
    client: AsyncClient,
    mock_db,
    mock_operator_user,
    mock_scope_a,
    mock_asset_a,
) -> None:
    """Test GET /api/v1/reports/assets/{id} with ownership validations."""
    mock_get_user.return_value = mock_operator_user
    setup_mock_db_queries(mock_db, assets=[mock_asset_a], scope=mock_scope_a)

    CorrelationSnapshotService._snapshots[ASSET_A_ID] = {"exposure": "EXTERNAL"}
    AssetRiskSnapshotService._snapshots[ASSET_A_ID] = {"risk_score": 10}

    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.get(f"/api/v1/reports/assets/{ASSET_A_ID}", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["asset"]["id"] == str(ASSET_A_ID)


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_asset_report_api_ownership_block(
    mock_get_user,
    client: AsyncClient,
    mock_db,
    mock_operator_user,
    mock_scope_a,
    mock_asset_a,
) -> None:
    """Test GET /api/v1/reports/assets/{id} rejects users not owning the scope."""
    # Operator is USER_A_ID but scope owner is USER_B_ID
    mock_get_user.return_value = mock_operator_user
    mock_scope_a.owner_id = USER_B_ID  # Ownership mismatch
    setup_mock_db_queries(mock_db, assets=[mock_asset_a], scope=mock_scope_a)

    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.get(f"/api/v1/reports/assets/{ASSET_A_ID}", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_findings_report_api(
    mock_get_user, client: AsyncClient, mock_db, mock_operator_user
) -> None:
    """Test GET /api/v1/reports/findings endpoint."""
    mock_get_user.return_value = mock_operator_user
    setup_mock_db_queries(mock_db)

    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.get(
        "/api/v1/reports/findings?severity=high", headers=headers
    )
    assert response.status_code == 200


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_risk_report_api(
    mock_get_user, client: AsyncClient, mock_db, mock_reader_user
) -> None:
    """Test GET /api/v1/reports/risk endpoint."""
    mock_get_user.return_value = mock_reader_user
    setup_mock_db_queries(mock_db)

    headers = get_auth_header(USER_B_ID, "reader")
    response = await client.get("/api/v1/reports/risk", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_exposure_report_api(
    mock_get_user, client: AsyncClient, mock_db, mock_reader_user
) -> None:
    """Test GET /api/v1/reports/exposure endpoint."""
    mock_get_user.return_value = mock_reader_user
    setup_mock_db_queries(mock_db)

    headers = get_auth_header(USER_B_ID, "reader")
    response = await client.get("/api/v1/reports/exposure", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_dashboard_summary_api(
    mock_get_user, client: AsyncClient, mock_db, mock_reader_user
) -> None:
    """Test GET /api/v1/dashboard/summary endpoint."""
    mock_get_user.return_value = mock_reader_user
    DashboardService._cache = {"asset_count": 0}

    headers = get_auth_header(USER_B_ID, "reader")
    response = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_dashboard_trends_api(
    mock_get_user, client: AsyncClient, mock_db, mock_reader_user
) -> None:
    """Test GET /api/v1/dashboard/trends endpoint."""
    mock_get_user.return_value = mock_reader_user
    setup_mock_db_queries(mock_db)

    headers = get_auth_header(USER_B_ID, "reader")
    response = await client.get("/api/v1/dashboard/trends", headers=headers)
    assert response.status_code == 200


# --- Export Endpoint API Tests ---


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_export_executive_json_api(
    mock_get_user, client: AsyncClient, mock_db, mock_reader_user
) -> None:
    """Test GET /api/v1/reports/executive/export/json endpoint."""
    mock_get_user.return_value = mock_reader_user
    ExecutiveReportService._cache = {"summary": {}}

    headers = get_auth_header(USER_B_ID, "reader")
    response = await client.get(
        "/api/v1/reports/executive/export/json", headers=headers
    )
    assert response.status_code == 200
    assert (
        response.headers["Content-Disposition"]
        == 'attachment; filename="executive_report.json"'
    )


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_export_executive_csv_api(
    mock_get_user, client: AsyncClient, mock_db, mock_reader_user
) -> None:
    """Test GET /api/v1/reports/executive/export/csv endpoint."""
    mock_get_user.return_value = mock_reader_user
    ExecutiveReportService._cache = {"summary": {}}

    headers = get_auth_header(USER_B_ID, "reader")
    response = await client.get("/api/v1/reports/executive/export/csv", headers=headers)
    assert response.status_code == 200
    assert (
        response.headers["Content-Disposition"]
        == 'attachment; filename="executive_report.csv"'
    )


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_export_asset_json_api(
    mock_get_user,
    client: AsyncClient,
    mock_db,
    mock_operator_user,
    mock_scope_a,
    mock_asset_a,
) -> None:
    """Test GET /api/v1/reports/assets/{id}/export/json endpoint."""
    mock_get_user.return_value = mock_operator_user
    setup_mock_db_queries(mock_db, assets=[mock_asset_a], scope=mock_scope_a)

    CorrelationSnapshotService._snapshots[ASSET_A_ID] = {}
    AssetRiskSnapshotService._snapshots[ASSET_A_ID] = {}

    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.get(
        f"/api/v1/reports/assets/{ASSET_A_ID}/export/json", headers=headers
    )
    assert response.status_code == 200
    assert f"asset_report_{ASSET_A_ID}.json" in response.headers["Content-Disposition"]


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_export_asset_csv_api(
    mock_get_user,
    client: AsyncClient,
    mock_db,
    mock_operator_user,
    mock_scope_a,
    mock_asset_a,
) -> None:
    """Test GET /api/v1/reports/assets/{id}/export/csv endpoint."""
    mock_get_user.return_value = mock_operator_user
    setup_mock_db_queries(mock_db, assets=[mock_asset_a], scope=mock_scope_a)

    CorrelationSnapshotService._snapshots[ASSET_A_ID] = {}
    AssetRiskSnapshotService._snapshots[ASSET_A_ID] = {}

    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.get(
        f"/api/v1/reports/assets/{ASSET_A_ID}/export/csv", headers=headers
    )
    assert response.status_code == 200
    assert f"asset_report_{ASSET_A_ID}.csv" in response.headers["Content-Disposition"]


# ==============================================================================
# 4. RESILIENCE & STABILITY TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_empty_database_handling(mock_db) -> None:
    """Stability: Dashboard summaries complete with zero values on empty db."""
    setup_mock_db_queries(mock_db, assets=[], ports=[], services=[], findings=[])
    DashboardService.clear_cache()

    stats = await DashboardService.get_dashboard_summary(mock_db, bypass_cache=True)
    assert stats["asset_count"] == 0
    assert stats["internet_exposed_assets"] == 0
    assert stats["findings"]["critical"] == 0


@pytest.mark.asyncio
async def test_missing_asset_handling(mock_db) -> None:
    """Stability: Asset report generation on non-existent asset ID returns None."""
    setup_mock_db_queries(mock_db, assets=[])
    report = await AssetReportService.generate_asset_report(mock_db, uuid.uuid4())
    assert report is None


@pytest.mark.asyncio
async def test_large_dataset_aggregation(mock_db) -> None:
    """Stability: Service aggregates large asset volumes without crashing."""
    large_assets = []
    for i in range(1000):
        a = Asset()
        a.id = uuid.uuid4()
        a.deleted_at = None
        large_assets.append(a)

    setup_mock_db_queries(mock_db, assets=large_assets)
    DashboardService.clear_cache()

    stats = await DashboardService.get_dashboard_summary(mock_db, bypass_cache=True)
    assert stats["asset_count"] == 1000


@pytest.mark.asyncio
async def test_dashboard_cache_invalidation(mock_db) -> None:
    """Test that dashboard cache invalidates properly."""
    from src.services.report_cache_service import ReportCacheService

    # 1. Prime cache
    DashboardService._cache = {"mock_stats": "dashboard"}

    # 2. Verify cache is used
    res = await DashboardService.get_dashboard_summary(mock_db)
    assert res == {"mock_stats": "dashboard"}

    # 3. Call invalidate_dashboard_cache
    ReportCacheService.invalidate_dashboard_cache()

    # 4. Verify cache is cleared
    assert DashboardService._cache is None


@pytest.mark.asyncio
async def test_executive_cache_invalidation(mock_db) -> None:
    """Test that executive report cache invalidates properly."""
    from src.services.report_cache_service import ReportCacheService

    # 1. Prime cache
    ExecutiveReportService._cache = {"mock_report": "executive"}

    # 2. Verify cache is used
    res = await ExecutiveReportService.get_executive_report(mock_db)
    assert res == {"mock_report": "executive"}

    # 3. Call invalidate_executive_cache
    ReportCacheService.invalidate_executive_cache()

    # 4. Verify cache is cleared
    assert ExecutiveReportService._cache is None


@pytest.mark.asyncio
async def test_asset_report_cache_invalidation(mock_db) -> None:
    """Test that asset report cache invalidates properly upon finding updates."""
    from src.infrastructure.database.models import Finding
    from src.services.finding_service import FindingService
    from src.services.report_cache_service import ReportCacheService

    # Setup mock assets & findings
    asset_id = uuid.uuid4()
    asset = Asset()
    asset.id = asset_id
    asset.scope_id = SCOPE_A_ID
    asset.host = "test-cache.com"
    asset.ip = "1.2.3.4"
    asset.asset_type = "domain"
    asset.deleted_at = None

    finding = Finding()
    finding.id = uuid.uuid4()
    finding.asset_id = asset_id
    finding.title = "Test Cache Finding"
    finding.severity = "high"
    finding.status = "open"
    finding.template_id = "test-c-1"
    finding.fingerprint = "fp123"
    finding.metadata_json = {}
    finding.first_seen = datetime.now(timezone.utc)
    finding.last_seen = datetime.now(timezone.utc)

    setup_mock_db_queries(mock_db, assets=[asset], findings=[finding])

    # Extend get_mock to return our finding
    original_get = mock_db.get

    async def custom_get(model_cls, pk):
        if model_cls.__name__ == "Finding" and pk == finding.id:
            return finding
        return await original_get(model_cls, pk)

    mock_db.get = AsyncMock(side_effect=custom_get)

    # Clear caches
    ReportCacheService.invalidate_all()

    # 1. Generate report to cache it
    report1 = await AssetReportService.generate_asset_report(mock_db, asset_id)
    assert report1 is not None
    assert asset_id in AssetReportService._cache

    # 2. Modify finding status using FindingService (which invalidates)
    with patch(
        "src.services.finding_service.FindingSnapshotService.update_finding_snapshot",
        new_callable=AsyncMock,
    ):
        await FindingService.update_status(
            mock_db,
            finding_id=finding.id,
            new_status="resolved",
            actor_id=None,
        )

    # 3. Verify asset report cache is cleared
    assert asset_id not in AssetReportService._cache


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_dashboard_trend_windowing(
    mock_get_user, client: AsyncClient, mock_db, mock_operator_user
) -> None:
    """Test dashboard trend endpoints with window validation (7, 30, 90, 365)."""
    mock_get_user.return_value = mock_operator_user
    headers = get_auth_header(USER_A_ID, "operator")

    # Test valid days (7, 30, 90, 365)
    for days in [7, 30, 90, 365]:
        with patch(
            "src.services.dashboard_trend_service.DashboardTrendService.generate_trends",
            new_callable=AsyncMock,
        ) as mock_gen:
            mock_gen.return_value = {
                "risk_trend": [],
                "finding_trend": [],
                "critical_finding_trend": [],
            }
            response = await client.get(
                f"/api/v1/dashboard/trends?days={days}", headers=headers
            )
            assert response.status_code == 200
            assert response.json()["data"]["window_days"] == days
            mock_gen.assert_called_once_with(mock_db, days)

    # Test invalid days (must be HTTP 400)
    for invalid_days in [5, 10, 100, 366]:
        response = await client.get(
            f"/api/v1/dashboard/trends?days={invalid_days}", headers=headers
        )
        assert response.status_code == 400
        err_msg = response.json()["error"]["message"]
        assert (
            "Invalid trend window" in err_msg or "Invalid trend window days" in err_msg
        )


def test_export_metadata_present() -> None:
    """Test wrap JSON exports with metadata and CSV exports with comments."""
    # JSON test
    dummy_report = {"summary": {"asset_count": 5}, "top_risky_assets": []}
    result_json = ExportService.export_executive_report_json(dummy_report)
    parsed = json.loads(result_json)

    assert parsed["report_version"] == "1.0"
    assert "generated_at" in parsed
    assert parsed["generated_by"] == "AegisX"
    assert parsed["data"] == dummy_report

    # CSV test (executive)
    result_csv = ExportService.export_executive_report_csv(dummy_report)
    lines = result_csv.strip().split("\n")
    assert lines[0].startswith("# Report Version: 1.0")
    assert lines[1].startswith("# Generated By: AegisX")
    assert lines[2].startswith("# Generated At:")
