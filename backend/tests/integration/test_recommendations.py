import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from src.core.security import create_access_token
from src.infrastructure.database.models import Asset, Finding, Scope, User, Workflow

# Standard IDs for testing
ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OPERATOR_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
READER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")

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
    f.title = "Test Vulnerability"
    f.description = "Vulnerability description"
    f.severity = "high"
    f.status = "open"
    f.template_id = "test-tpl"
    f.template_name = "Test Tpl"
    f.source_plugin = "nuclei"
    f.first_seen = datetime.now(timezone.utc)
    f.last_seen = datetime.now(timezone.utc)
    f.created_at = datetime.now(timezone.utc)
    f.updated_at = datetime.now(timezone.utc)
    f.fingerprint = "test-finding-fp"
    f.metadata_json = {}
    return f


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


# --- Unit Tests ---


def test_priority_score_normalization() -> None:
    """Requirement: Prioritization base weights must sum up to exactly 100."""
    from src.services.priority_factor_registry import PriorityFactorRegistry

    total_weight = sum(PriorityFactorRegistry.WEIGHTS.values())
    assert total_weight == 100.0


@pytest.mark.asyncio
async def test_recommendation_deduplication(mock_db, mock_asset, mock_finding) -> None:
    """Requirement: Verify repeated scans do not create duplicate recommendations
    for the same asset/finding context.
    """
    from src.services.recommendation_history_service import RecommendationHistoryService
    from src.services.recommendation_service import RecommendationService

    RecommendationHistoryService.clear_history()

    # Mock DB queries
    mock_db.get = AsyncMock(
        side_effect=lambda model, ident: (
            mock_asset
            if model == Asset
            else (mock_finding if model == Finding else None)
        )
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_finding]
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    # Mock snapshots
    with patch(
        "src.services.asset_risk_snapshot_service.AssetRiskSnapshotService.get_snapshot",
        return_value={"risk_score": 85, "criticality": "HIGH"},
    ), patch(
        "src.services.correlation_snapshot_service.CorrelationSnapshotService.get_snapshot",
        return_value={"exposure": "EXTERNAL"},
    ):

        recs1 = await RecommendationService.generate_asset_recommendations(
            mock_db, ASSET_ID
        )
        assert len(recs1) > 0

        # Second generation
        recs2 = await RecommendationService.generate_asset_recommendations(
            mock_db, ASSET_ID
        )
        assert len(recs2) == len(recs1)

        # History check: fingerprint should exist and be unique
        history = RecommendationHistoryService._history
        assert len(history) == len(recs1)
        for entry in history.values():
            assert entry["times_recomputed"] == 1  # 0 initially, then 1 after recompute


@pytest.mark.asyncio
async def test_recommendation_priority_change(mock_db) -> None:
    """Requirement: Verify recommendation priority changes generate events,
    history records, and audit log entries.
    """
    from src.services.recommendation_history_service import RecommendationHistoryService

    RecommendationHistoryService.clear_history()

    fp = "test-fp-priority-change"
    asset_id = str(ASSET_ID)

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # 1. Record recommendation (creation)
    await RecommendationHistoryService.record_recommendation(
        db=mock_db,
        fingerprint=fp,
        asset_id=asset_id,
        finding_id=None,
        priority="MEDIUM",
        title="Harden asset configurations",
    )

    assert RecommendationHistoryService._history[fp]["priority"] == "MEDIUM"

    # 2. Record recommendation with upgraded priority
    await RecommendationHistoryService.record_recommendation(
        db=mock_db,
        fingerprint=fp,
        asset_id=asset_id,
        finding_id=None,
        priority="HIGH",
        title="Harden asset configurations",
    )

    assert RecommendationHistoryService._history[fp]["priority"] == "HIGH"
    assert RecommendationHistoryService._history[fp]["times_recomputed"] == 1
    assert mock_db.add.called


@pytest.mark.asyncio
async def test_recommendation_aging_preserved_after_recompute(mock_db) -> None:
    """Requirement: Verify created_at remains unchanged, last_seen updates,
    and times_recomputed increments.
    """
    import time

    from src.services.recommendation_history_service import RecommendationHistoryService

    RecommendationHistoryService.clear_history()

    fp = "test-fp-aging"
    asset_id = str(ASSET_ID)

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # Create recommendation
    await RecommendationHistoryService.record_recommendation(
        db=mock_db,
        fingerprint=fp,
        asset_id=asset_id,
        finding_id=None,
        priority="LOW",
        title="Check software version",
    )

    first_entry = RecommendationHistoryService._history[fp]
    created_at_first = first_entry["created_at"]
    last_seen_first = first_entry["last_seen"]
    assert first_entry["times_recomputed"] == 0

    time.sleep(0.001)

    # Recompute recommendation
    await RecommendationHistoryService.record_recommendation(
        db=mock_db,
        fingerprint=fp,
        asset_id=asset_id,
        finding_id=None,
        priority="LOW",
        title="Check software version",
    )

    second_entry = RecommendationHistoryService._history[fp]
    assert second_entry["created_at"] == created_at_first
    assert second_entry["last_seen"] > last_seen_first
    assert second_entry["times_recomputed"] == 1


@pytest.mark.asyncio
async def test_guidance_generation(mock_db, mock_asset, mock_finding) -> None:
    """Verify structured guidance generation logic for critical/high/rediscovered
    finding, external asset, high-risk asset.
    """
    from src.services.investigation_assistance_service import (
        InvestigationAssistanceService,
    )

    mock_db.get = AsyncMock(
        side_effect=lambda model, ident: (
            mock_asset
            if model == Asset
            else (mock_finding if model == Finding else None)
        )
    )

    # Test asset guidance
    mock_finding.severity = "critical"
    # Make rediscovered
    mock_finding.first_seen = datetime.now(timezone.utc) - timedelta(days=1)
    mock_finding.last_seen = datetime.now(timezone.utc)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_finding]
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch(
        "src.services.asset_risk_snapshot_service.AssetRiskSnapshotService.get_snapshot",
        return_value={"risk_score": 85, "criticality": "HIGH"},
    ), patch(
        "src.services.correlation_snapshot_service.CorrelationSnapshotService.get_snapshot",
        return_value={"exposure": "EXTERNAL"},
    ):

        asset_guidance = await InvestigationAssistanceService.generate_asset_guidance(
            mock_db, ASSET_ID
        )
        assert len(asset_guidance.steps) > 0
        assert (
            "Verify if the critical vulnerability is exposed to the internet."
            in asset_guidance.steps
        )
        assert (
            "Review past resolution records for recurrent patterns."
            in asset_guidance.steps
        )
        assert (
            "Audit ingress firewall rules to minimize public exposure."
            in asset_guidance.steps
        )
        assert (
            "Schedule immediate vulnerability remediation scan." in asset_guidance.steps
        )

        # Test finding guidance
        finding_guidance = (
            await InvestigationAssistanceService.generate_finding_guidance(
                mock_db, FINDING_ID
            )
        )
        assert len(finding_guidance.steps) > 0
        assert (
            "Verify exploitability using non-intrusive security tools."
            in finding_guidance.steps
        )
        assert (
            "Verify why previous resolution status did not persist."
            in finding_guidance.steps
        )


@pytest.mark.asyncio
async def test_copilot_context_integration(mock_db) -> None:
    """Verify that recommendations and snapshot are correctly integrated
    in AIContextBuilder outputs.
    """
    from src.services.ai_context_builder import AIContextBuilder

    # Mock asset report
    mock_report = {
        "asset": {"id": str(ASSET_ID)},
        "exposure": {},
        "risk": {},
        "findings": [],
        "ports": [],
        "services": [],
        "technologies": [],
    }

    with patch(
        "src.services.asset_report_service.AssetReportService.generate_asset_report",
        return_value=mock_report,
    ), patch(
        "src.services.recommendation_service.RecommendationService.generate_asset_recommendations",
        return_value=[],
    ), patch(
        "src.services.recommendation_snapshot_service.RecommendationSnapshotService.get_snapshot",
        return_value={"total": 0},
    ):

        context = await AIContextBuilder.build_asset_context(mock_db, ASSET_ID)
        assert "recommendations" in context
        assert "recommendation_snapshot" in context["asset"]
        assert context["asset"]["recommendation_snapshot"] == {"total": 0}


# --- Endpoint RBAC & Scope Ownership Integration Tests ---


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_api_get_asset_recommendations_admin_allowed(
    mock_get_user,
    client: AsyncClient,
    mock_admin: User,
    mock_asset: Asset,
    mock_db: AsyncMock,
) -> None:
    """Verify admin role is allowed access to recommendations."""
    mock_get_user.return_value = mock_admin
    mock_db.get = AsyncMock(return_value=mock_asset)

    with patch(
        "src.services.recommendation_service.RecommendationService.generate_asset_recommendations",
        return_value=[],
    ):
        headers = get_auth_header(ADMIN_ID, "admin")
        response = await client.get(
            f"/api/v1/recommendations/assets/{ASSET_ID}", headers=headers
        )
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_api_get_asset_recommendations_reader_blocked(
    mock_get_user,
    client: AsyncClient,
    mock_reader: User,
) -> None:
    """Verify reader role is blocked from recommendations (RBAC)."""
    mock_get_user.return_value = mock_reader

    headers = get_auth_header(READER_ID, "reader")
    response = await client.get(
        f"/api/v1/recommendations/assets/{ASSET_ID}", headers=headers
    )
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["error"]["message"]


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.recommendations.get_scope_by_id")
async def test_api_get_asset_recommendations_operator_owner_allowed(
    mock_get_scope,
    mock_get_user,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
    mock_asset: Asset,
    mock_db: AsyncMock,
) -> None:
    """Verify operator role who owns the scope is allowed access."""
    mock_get_user.return_value = mock_operator
    mock_get_scope.return_value = mock_scope
    mock_db.get = AsyncMock(return_value=mock_asset)

    with patch(
        "src.services.recommendation_service.RecommendationService.generate_asset_recommendations",
        return_value=[],
    ):
        headers = get_auth_header(OPERATOR_ID, "operator")
        response = await client.get(
            f"/api/v1/recommendations/assets/{ASSET_ID}", headers=headers
        )
        assert response.status_code == 200


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.recommendations.get_scope_by_id")
async def test_api_get_asset_recommendations_operator_non_owner_blocked(
    mock_get_scope,
    mock_get_user,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
    mock_asset: Asset,
    mock_db: AsyncMock,
) -> None:
    """Verify operator role who does NOT own the scope is blocked (403)."""
    # Scope owner is different
    mock_scope.owner_id = uuid.uuid4()
    mock_get_user.return_value = mock_operator
    mock_get_scope.return_value = mock_scope
    mock_db.get = AsyncMock(return_value=mock_asset)

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.get(
        f"/api/v1/recommendations/assets/{ASSET_ID}", headers=headers
    )
    assert response.status_code == 403
    assert "You do not have permissions" in response.json()["error"]["message"]


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.recommendations.get_scope_by_id")
async def test_api_get_finding_recommendations_operator_owner_allowed(
    mock_get_scope,
    mock_get_user,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
    mock_finding: Finding,
    mock_asset: Asset,
    mock_db: AsyncMock,
) -> None:
    """Verify operator who owns finding's parent scope is allowed
    finding recommendations.
    """
    mock_get_user.return_value = mock_operator
    mock_get_scope.return_value = mock_scope
    mock_db.get = AsyncMock(
        side_effect=lambda model, ident: (
            mock_finding
            if model == Finding
            else (mock_asset if model == Asset else None)
        )
    )

    with patch(
        "src.services.recommendation_service.RecommendationService.generate_finding_recommendations",
        return_value=[],
    ):
        headers = get_auth_header(OPERATOR_ID, "operator")
        response = await client.get(
            f"/api/v1/recommendations/findings/{FINDING_ID}", headers=headers
        )
        assert response.status_code == 200


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.recommendations.get_scope_by_id")
async def test_api_get_asset_guidance_operator_owner_allowed(
    mock_get_scope,
    mock_get_user,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
    mock_asset: Asset,
    mock_db: AsyncMock,
) -> None:
    """Verify operator who owns scope is allowed investigation guidance."""
    mock_get_user.return_value = mock_operator
    mock_get_scope.return_value = mock_scope
    mock_db.get = AsyncMock(return_value=mock_asset)

    from src.domain.entities.recommendation import InvestigationGuidanceResponse

    guidance_resp = InvestigationGuidanceResponse(
        finding_id=None, asset_id=str(ASSET_ID), steps=[]
    )

    with patch(
        "src.services.investigation_assistance_service.InvestigationAssistanceService.generate_asset_guidance",
        return_value=guidance_resp,
    ):
        headers = get_auth_header(OPERATOR_ID, "operator")
        response = await client.get(
            f"/api/v1/recommendations/assets/{ASSET_ID}/guidance", headers=headers
        )
        assert response.status_code == 200
