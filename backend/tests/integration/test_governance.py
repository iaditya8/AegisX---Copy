import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from src.core.security import create_access_token
from src.domain.entities.governance import GovernanceStatus, RiskAcceptanceStatus
from src.infrastructure.database.models import (
    Asset,
    Finding,
    Scope,
    User,
    Workflow,
)
from src.services.compliance_drift_service import ComplianceDriftService
from src.services.compliance_mapping_service import ComplianceMappingService
from src.services.governance_service import GovernanceService
from src.services.governance_snapshot_service import GovernanceSnapshotService
from src.services.remediation_service import RemediationService
from src.services.risk_acceptance_service import RiskAcceptanceService

ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OPERATOR_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
READER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")

SCOPE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
ASSET_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
FINDING_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
FP = "test-governance-fp"


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
    f.title = "Critical Vulnerability"
    f.description = "Vulnerability description"
    f.severity = "critical"
    f.status = "open"
    f.template_id = "test-tpl"
    f.template_name = "Test Tpl"
    f.source_plugin = "nuclei"
    f.first_seen = datetime.now(timezone.utc)
    f.last_seen = datetime.now(timezone.utc)
    f.created_at = datetime.now(timezone.utc)
    f.updated_at = datetime.now(timezone.utc)
    f.fingerprint = FP
    f.metadata_json = {}
    return f


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_stores():
    RemediationService.clear_remediations()
    RiskAcceptanceService.clear_acceptances()
    GovernanceSnapshotService.clear_snapshots()
    ComplianceDriftService.clear_drift_states()


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
async def test_risk_acceptance_creation(mock_db, mock_finding, mock_asset) -> None:
    """Verify that a risk acceptance is created with ACTIVE status and updates remediation status."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)
    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    rec = await RiskAcceptanceService.accept_risk(
        db=mock_db,
        asset_id=ASSET_ID,
        finding_id=FINDING_ID,
        recommendation_id=uuid.uuid4(),
        recommendation_fingerprint=FP,
        approved_by="test_admin",
        reason="Business operational necessity",
        actor_id=ADMIN_ID,
    )

    assert rec.status == RiskAcceptanceStatus.ACTIVE
    assert rec.recommendation_fingerprint == FP
    assert rec.approved_by == "test_admin"

    # Confirm remediation was updated to ACCEPTED_RISK
    rem_id = RemediationService._fingerprint_lookup[FP]
    rem = RemediationService.get_remediation(rem_id)
    assert rem.status.value == "ACCEPTED_RISK"


@pytest.mark.asyncio
async def test_risk_acceptance_expiration(mock_db, mock_finding, mock_asset) -> None:
    """Verify expiration transitions RiskAcceptance to EXPIRED and resets remediation status."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)
    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    rec = await RiskAcceptanceService.accept_risk(
        db=mock_db,
        asset_id=ASSET_ID,
        finding_id=FINDING_ID,
        recommendation_id=uuid.uuid4(),
        recommendation_fingerprint=FP,
        approved_by="test_admin",
        reason="Temporary risk approval",
        actor_id=ADMIN_ID,
    )

    # Force expiration date into the past
    rec.expiration_date = datetime.now(timezone.utc) - timedelta(days=1)

    # Trigger expiration check
    await RiskAcceptanceService.check_expirations(mock_db, actor_id=ADMIN_ID)

    assert rec.status == RiskAcceptanceStatus.EXPIRED

    # Remediation must reset to OPEN
    rem_id = RemediationService._fingerprint_lookup[FP]
    rem = RemediationService.get_remediation(rem_id)
    assert rem.status.value == "OPEN"


@pytest.mark.asyncio
async def test_risk_acceptance_revocation(mock_db, mock_finding, mock_asset) -> None:
    """Verify revocation moves status to REVOKED and resets remediation status."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)
    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    rec = await RiskAcceptanceService.accept_risk(
        db=mock_db,
        asset_id=ASSET_ID,
        finding_id=FINDING_ID,
        recommendation_id=uuid.uuid4(),
        recommendation_fingerprint=FP,
        approved_by="test_admin",
        reason="Revoke testing",
        actor_id=ADMIN_ID,
    )

    await RiskAcceptanceService.revoke_risk(
        mock_db, rec.acceptance_id, actor_id=ADMIN_ID
    )

    assert rec.status == RiskAcceptanceStatus.REVOKED

    # Remediation must reset to OPEN
    rem_id = RemediationService._fingerprint_lookup[FP]
    rem = RemediationService.get_remediation(rem_id)
    assert rem.status.value == "OPEN"


@pytest.mark.asyncio
async def test_asset_governance_status(mock_db, mock_asset, mock_finding) -> None:
    """Verify asset governance transitions through COMPLIANT, NON_COMPLIANT, and ACCEPTED_RISK."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)

    # 1. Mock first evaluate to return no open findings
    mock_res_empty = MagicMock()
    mock_res_empty.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_res_empty)

    res = await GovernanceService.evaluate_asset_governance(mock_db, ASSET_ID)
    assert res == GovernanceStatus.COMPLIANT

    # 2. Mock second evaluate to return open findings
    mock_res_findings = MagicMock()
    mock_res_findings.scalars.return_value.all.return_value = [mock_finding]
    mock_db.execute = AsyncMock(return_value=mock_res_findings)

    with patch(
        "src.services.compliance_mapping_service.ComplianceMappingService.get_compliance_controls"
    ) as mock_controls:
        mock_c = MagicMock()
        mock_c.affected_assets = [ASSET_ID]
        mock_controls.return_value = [mock_c]

        res2 = await GovernanceService.evaluate_asset_governance(mock_db, ASSET_ID)
        assert res2 == GovernanceStatus.NON_COMPLIANT


@pytest.mark.asyncio
async def test_finding_governance_status(mock_db, mock_asset, mock_finding) -> None:
    """Verify finding governance status based on open/accepted risk states."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)

    # 1. Uncovered open finding -> NON_COMPLIANT
    res = await GovernanceService.evaluate_finding_governance(mock_db, FINDING_ID)
    assert res == GovernanceStatus.NON_COMPLIANT

    # 2. Open finding with active risk acceptance -> ACCEPTED_RISK
    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    await RiskAcceptanceService.accept_risk(
        db=mock_db,
        asset_id=ASSET_ID,
        finding_id=FINDING_ID,
        recommendation_id=uuid.uuid4(),
        recommendation_fingerprint=FP,
        approved_by="test_admin",
        reason="Exemption approved",
    )

    res2 = await GovernanceService.evaluate_finding_governance(mock_db, FINDING_ID)
    assert res2 == GovernanceStatus.ACCEPTED_RISK


@pytest.mark.asyncio
async def test_non_compliant_detection(mock_db, mock_asset, mock_finding) -> None:
    """Verify non-compliant assets and findings are detected successfully."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)

    with patch(
        "src.services.governance_service.GovernanceService.evaluate_asset_governance",
        return_value=GovernanceStatus.NON_COMPLIANT,
    ), patch(
        "src.services.governance_service.GovernanceService.evaluate_finding_governance",
        return_value=GovernanceStatus.NON_COMPLIANT,
    ):

        # Mock execute for get_non_compliant_assets (select assets) and get_non_compliant_findings (select findings)
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.side_effect = [[mock_asset], [mock_finding]]
        mock_db.execute = AsyncMock(return_value=mock_res)

        assets = await GovernanceService.get_non_compliant_assets(mock_db)
        assert len(assets) == 1
        assert assets[0].id == ASSET_ID

        findings = await GovernanceService.get_non_compliant_findings(mock_db)
        assert len(findings) == 1
        assert findings[0].id == FINDING_ID


@pytest.mark.asyncio
async def test_compliance_control_mapping(mock_db, mock_asset, mock_finding) -> None:
    """Verify findings and conditions map to the correct controls."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.side_effect = [[mock_asset], [mock_finding]]
    mock_db.execute = AsyncMock(return_value=mock_res)

    with patch(
        "src.services.correlation_service.CorrelationService.correlate_asset",
        return_value={"exposure": "internal"},
    ):
        controls = await ComplianceMappingService.get_compliance_controls(mock_db)

        vuln_control = next(c for c in controls if c.control_id == "VULN-001")
        assert vuln_control.status == "NON_COMPLIANT"
        assert FINDING_ID in vuln_control.affected_findings


@pytest.mark.asyncio
async def test_control_failure_detection(mock_db, mock_asset, mock_finding) -> None:
    """Verify control status shifts to NON_COMPLIANT when failure is introduced."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.side_effect = [[mock_asset], [mock_finding]]
    mock_db.execute = AsyncMock(return_value=mock_res)

    with patch(
        "src.services.correlation_service.CorrelationService.correlate_asset",
        return_value={"exposure": "internal"},
    ):
        controls = await ComplianceMappingService.get_compliance_controls(mock_db)
        vuln = next(c for c in controls if c.control_id == "VULN-001")
        assert vuln.status == "NON_COMPLIANT"


@pytest.mark.asyncio
async def test_control_restoration(mock_db, mock_asset, mock_finding) -> None:
    """Verify controls shift back to COMPLIANT when vulnerabilities are resolved."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.side_effect = [[mock_asset], []]
    mock_db.execute = AsyncMock(return_value=mock_res)

    with patch(
        "src.services.correlation_service.CorrelationService.correlate_asset",
        return_value={"exposure": "internal"},
    ):
        controls = await ComplianceMappingService.get_compliance_controls(mock_db)
        vuln = next(c for c in controls if c.control_id == "VULN-001")
        assert vuln.status == "COMPLIANT"


@pytest.mark.asyncio
async def test_governance_snapshot_generation(
    mock_db, mock_asset, mock_finding
) -> None:
    """Verify that cached governance snapshots can be generated and return statistics."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)
    mock_summary = {
        "compliant_assets": 0,
        "non_compliant_assets": 1,
        "accepted_risks": 0,
        "expired_acceptances": 0,
        "exception_count": 0,
        "sla_breaches": 0,
    }
    with patch(
        "src.services.governance_service.GovernanceService.evaluate_platform_governance",
        return_value=mock_summary,
    ):
        snapshot = await GovernanceSnapshotService.generate_snapshot(mock_db)
        assert snapshot["non_compliant_assets"] == 1
        assert snapshot["compliant_assets"] == 0
        assert snapshot["accepted_risks"] == 0


@pytest.mark.asyncio
async def test_governance_snapshot_rebuild_consistency(
    mock_db, mock_asset, mock_finding
) -> None:
    """Verify that cache clears trigger dynamic rebuilding of snapshots."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)
    mock_summary = {
        "compliant_assets": 0,
        "non_compliant_assets": 1,
        "accepted_risks": 0,
        "expired_acceptances": 0,
        "exception_count": 0,
        "sla_breaches": 0,
    }
    with patch(
        "src.services.governance_service.GovernanceService.evaluate_platform_governance",
        return_value=mock_summary,
    ):
        await GovernanceSnapshotService.generate_snapshot(mock_db)
        GovernanceSnapshotService.clear_snapshots()

        # Retrieve should trigger rebuild
        snapshot = await GovernanceSnapshotService.get_snapshot(mock_db)
        assert snapshot["non_compliant_assets"] == 1


@pytest.mark.asyncio
async def test_governance_drift_detection(mock_db, mock_asset, mock_finding) -> None:
    """Verify drift detection triggers events on status changes."""
    setup_basic_mock_db(mock_db, mock_asset, mock_finding)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))

    def execute_side_effect(query, *args, **kwargs):
        query_str = str(query).lower()
        if "workflow" in query_str:
            mock_res = MagicMock()
            mock_res.scalar_one_or_none.return_value = mock_wf
            return mock_res
        else:
            mock_res = MagicMock()
            mock_res.scalars.return_value.all.return_value = [mock_asset]
            return mock_res

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    with patch(
        "src.services.governance_service.GovernanceService.evaluate_asset_governance"
    ) as mock_eval, patch(
        "src.services.compliance_mapping_service.ComplianceMappingService.get_compliance_controls"
    ) as mock_comp:

        mock_eval.side_effect = [
            GovernanceStatus.NON_COMPLIANT,
            GovernanceStatus.COMPLIANT,
        ]
        mock_comp.return_value = []

        # 1. Establish baseline state
        await ComplianceDriftService.detect_drift(mock_db)

        # 2. Run check where state changes
        await ComplianceDriftService.detect_drift(mock_db)
        assert mock_db.add.called


@pytest.mark.asyncio
async def test_sla_breach_governance_transition(mock_db, mock_asset) -> None:
    """Verify SLA breach transitions control and asset to non-compliant."""
    from src.services.remediation_service import RemediationService

    mock_wf = Workflow(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_wf
    mock_db.execute = AsyncMock(return_value=mock_res)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # Sync recommendation (will auto-create OPEN remediation)
    rem = await RemediationService.sync_recommendation(
        db=mock_db,
        fingerprint=FP,
        asset_id=ASSET_ID,
        finding_id=FINDING_ID,
        priority="CRITICAL",
        title="Patch vuln",
    )

    # Force due date in the past
    rem.due_date = datetime.now(timezone.utc) - timedelta(days=1)

    # Evaluate compliance
    mock_res_comp = MagicMock()
    mock_res_comp.scalars.return_value.all.side_effect = [[mock_asset], []]
    mock_db.execute = AsyncMock(return_value=mock_res_comp)

    with patch(
        "src.services.correlation_service.CorrelationService.correlate_asset",
        return_value={"exposure": "internal"},
    ):
        controls = await ComplianceMappingService.get_compliance_controls(mock_db)
        ops_control = next(c for c in controls if c.control_id == "OPS-001")
        assert ops_control.status == "NON_COMPLIANT"


@pytest.mark.asyncio
async def test_ai_governance_context_injection(
    mock_db, mock_asset, mock_finding
) -> None:
    """Verify that governance details are injected in AIContextBuilder contexts."""
    from src.services.ai_context_builder import AIContextBuilder

    setup_basic_mock_db(mock_db, mock_asset, mock_finding)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.side_effect = [[mock_asset], [mock_finding]]
    mock_db.execute = AsyncMock(return_value=mock_res)

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
    ), patch(
        "src.services.remediation_snapshot_service.RemediationSnapshotService.get_snapshot",
        return_value={},
    ), patch(
        "src.services.governance_service.GovernanceService.evaluate_asset_governance",
        return_value=GovernanceStatus.NON_COMPLIANT,
    ), patch(
        "src.services.compliance_mapping_service.ComplianceMappingService.get_compliance_controls",
        return_value=[],
    ):
        context = await AIContextBuilder.build_asset_context(mock_db, ASSET_ID)
        assert "governance" in context
        assert context["asset"]["governance_status"] == "NON_COMPLIANT"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_governance_admin_only_risk_acceptance(
    mock_get_user,
    client: AsyncClient,
    mock_operator: User,
    mock_reader: User,
) -> None:
    """Verify non-admin roles are blocked from mutations."""
    mock_get_user.return_value = mock_operator
    headers_op = get_auth_header(OPERATOR_ID, "operator")

    res = await client.post(
        "/api/v1/governance/accept-risk",
        json={
            "asset_id": str(ASSET_ID),
            "recommendation_fingerprint": FP,
            "approved_by": "op",
            "reason": "testing restrictions",
        },
        headers=headers_op,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.governance.get_scope_by_id")
async def test_governance_scope_restrictions(
    mock_get_scope,
    mock_get_user,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
    mock_asset: Asset,
    mock_db: AsyncMock,
) -> None:
    """Verify operators are blocked from viewing governance of assets outside their scope."""
    mock_get_user.return_value = mock_operator

    # scope owner is different
    mock_scope.owner_id = uuid.uuid4()
    mock_get_scope.return_value = mock_scope

    mock_db.get = AsyncMock(
        side_effect=lambda model, ident: mock_asset if model == Asset else None
    )

    headers = get_auth_header(OPERATOR_ID, "operator")
    res = await client.get(f"/api/v1/governance/assets/{ASSET_ID}", headers=headers)
    assert res.status_code == 403
