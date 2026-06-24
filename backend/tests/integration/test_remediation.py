import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from src.core.security import create_access_token
from src.domain.entities.remediation import RemediationStatus
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


# --- Integration Tests ---


@pytest.mark.asyncio
async def test_auto_remediation_creation(mock_db) -> None:
    """Verify Recommendation Sync -> Auto-Remediation Creation -> OPEN -> Due Date."""
    from src.services.remediation_history_service import (
        RemediationHistoryService,
    )
    from src.services.remediation_service import RemediationService

    RemediationService.clear_remediations()
    RemediationHistoryService.clear_history()

    # Mock workflow query for events
    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    fp = "test-fp-auto-remediation"

    rec = await RemediationService.sync_recommendation(
        db=mock_db,
        fingerprint=fp,
        asset_id=ASSET_ID,
        finding_id=FINDING_ID,
        priority="CRITICAL",
        title="Patch software vulnerability",
    )

    assert rec.status == RemediationStatus.OPEN
    assert rec.recommendation_fingerprint == fp
    # Critical priority SLA is 7 days
    expected_due = rec.created_at + timedelta(days=7)
    assert abs((rec.due_date - expected_due).total_seconds()) < 1.0

    # Check history is logged
    hist = RemediationHistoryService.get_history(rec.remediation_id)
    assert len(hist) == 1
    assert hist[0].history_type.value == "CREATED"


@pytest.mark.asyncio
async def test_remediation_sync_preserves_identity(mock_db) -> None:
    """Verify recommendation sync preserves remediation when fingerprint matches."""
    from src.services.remediation_history_service import (
        RemediationHistoryService,
    )
    from src.services.remediation_service import RemediationService

    RemediationService.clear_remediations()
    RemediationHistoryService.clear_history()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    fp = "test-fp-preservation"

    rec1 = await RemediationService.sync_recommendation(
        db=mock_db,
        fingerprint=fp,
        asset_id=ASSET_ID,
        finding_id=FINDING_ID,
        priority="HIGH",
        title="Check software updates",
    )

    rec_id1 = rec1.remediation_id

    # Sync again with different priority (should preserve same remediation)
    rec2 = await RemediationService.sync_recommendation(
        db=mock_db,
        fingerprint=fp,
        asset_id=ASSET_ID,
        finding_id=FINDING_ID,
        priority="CRITICAL",
        title="Check software updates",
    )

    assert rec2.remediation_id == rec_id1
    # Check due date is updated based on new priority (CRITICAL vs HIGH)
    expected_due = rec1.created_at + timedelta(days=7)
    assert abs((rec2.due_date - expected_due).total_seconds()) < 1.0


@pytest.mark.asyncio
async def test_invalid_status_transition(mock_db) -> None:
    """Verify invalid status transitions raise ValueError."""
    from src.services.remediation_service import RemediationService

    RemediationService.clear_remediations()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    rec = await RemediationService.sync_recommendation(
        db=mock_db,
        fingerprint="test-fp-invalid-trans",
        asset_id=ASSET_ID,
        finding_id=None,
        priority="LOW",
        title="Harden configurations",
    )

    # OPEN directly to REMEDIATED is invalid
    with pytest.raises(ValueError):
        await RemediationService.update_status(
            mock_db, rec.remediation_id, RemediationStatus.REMEDIATED
        )


@pytest.mark.asyncio
async def test_remediation_terminal_state_enforcement(mock_db) -> None:
    """Verify terminal status cannot transition further."""
    from src.services.remediation_service import RemediationService

    RemediationService.clear_remediations()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    rec = await RemediationService.sync_recommendation(
        db=mock_db,
        fingerprint="test-fp-terminal",
        asset_id=ASSET_ID,
        finding_id=None,
        priority="MEDIUM",
        title="Review firewall rules",
    )

    # Move to IN_PROGRESS then REMEDIATED
    await RemediationService.update_status(
        mock_db, rec.remediation_id, RemediationStatus.IN_PROGRESS
    )
    await RemediationService.update_status(
        mock_db, rec.remediation_id, RemediationStatus.REMEDIATED
    )

    # Trying to move from REMEDIATED to IN_PROGRESS should raise ValueError
    with pytest.raises(ValueError):
        await RemediationService.update_status(
            mock_db, rec.remediation_id, RemediationStatus.IN_PROGRESS
        )


@pytest.mark.asyncio
async def test_snapshot_rebuild_consistency(mock_db) -> None:
    """Verify that cached snapshots can be correctly rebuilt from active records."""
    from src.services.remediation_service import RemediationService
    from src.services.remediation_snapshot_service import (
        RemediationSnapshotService,
    )

    RemediationService.clear_remediations()
    RemediationSnapshotService.clear_snapshots()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # Sync recommendation (will auto-create OPEN remediation)
    await RemediationService.sync_recommendation(
        db=mock_db,
        fingerprint="test-fp-snap-rebuild",
        asset_id=ASSET_ID,
        finding_id=None,
        priority="HIGH",
        title="Check credentials",
    )

    # Clear the snapshot cache manually
    RemediationSnapshotService.clear_snapshots()

    # Retrieval should trigger rebuild
    snap = RemediationSnapshotService.get_snapshot(ASSET_ID)
    assert snap["open"] == 1
    assert snap["in_progress"] == 0


@pytest.mark.asyncio
async def test_ai_copilot_context_remediation_injection(mock_db) -> None:
    """Verify that remediation details are injected in AIContextBuilder contexts."""
    from src.services.ai_context_builder import AIContextBuilder
    from src.services.remediation_service import RemediationService
    from src.services.remediation_snapshot_service import (
        RemediationSnapshotService,
    )

    RemediationService.clear_remediations()
    RemediationSnapshotService.clear_snapshots()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # Create remediation
    await RemediationService.sync_recommendation(
        db=mock_db,
        fingerprint="test-fp-copilot",
        asset_id=ASSET_ID,
        finding_id=None,
        priority="LOW",
        title="Review software licenses",
    )

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
        return_value={},
    ):
        context = await AIContextBuilder.build_asset_context(mock_db, ASSET_ID)
        assert "remediation_snapshot" in context["asset"]
        assert context["asset"]["remediation_snapshot"]["open"] == 1


# --- API Endpoint Checks ---


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_api_remediations_rbac_reader_blocked(
    mock_get_user,
    client: AsyncClient,
    mock_reader: User,
) -> None:
    """Verify reader role is blocked from assigning owner (RBAC)."""
    mock_get_user.return_value = mock_reader

    headers = get_auth_header(READER_ID, "reader")
    response = await client.post(
        f"/api/v1/remediations/{uuid.uuid4()}/assign",
        json={"owner": "analyst"},
        headers=headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.remediations.get_scope_by_id")
async def test_api_remediations_scope_owner_allowed(
    mock_get_scope,
    mock_get_user,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
    mock_asset: Asset,
    mock_db: AsyncMock,
) -> None:
    """Verify operator who owns parent scope is allowed to assign owner."""
    mock_get_user.return_value = mock_operator
    mock_get_scope.return_value = mock_scope

    # Setup remediation record
    from src.services.remediation_service import RemediationService

    RemediationService.clear_remediations()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    rec = await RemediationService.sync_recommendation(
        db=mock_db,
        fingerprint="test-fp-api-allowed",
        asset_id=ASSET_ID,
        finding_id=None,
        priority="LOW",
        title="Check configs",
    )

    mock_db.get = AsyncMock(
        side_effect=lambda model, ident: mock_asset if model == Asset else None
    )

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.post(
        f"/api/v1/remediations/{rec.remediation_id}/assign",
        json={"owner": "john_doe"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["owner"] == "john_doe"
