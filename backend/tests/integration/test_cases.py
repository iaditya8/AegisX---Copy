import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.core.security import create_access_token
from src.domain.entities.case import (
    CaseSeverity,
    CaseStatus,
    ChainOfCustodyAction,
    EvidenceStatus,
)
from src.domain.entities.incident import IncidentSeverity, IncidentStatus
from src.infrastructure.database.models import Asset, Scope, User
from src.services.ai_context_builder import AIContextBuilder
from src.services.case_evidence_correlation_service import CaseEvidenceCorrelationService
from src.services.case_fingerprint_service import CaseFingerprintService
from src.services.case_history_service import CaseHistoryService
from src.services.case_severity_registry import CaseSeverityRegistry
from src.services.case_snapshot_service import CaseSnapshotService
from src.services.custody_service import CustodyService
from src.services.evidence_service import EvidenceRecord, EvidenceService
from src.services.case_service import CaseRecord, CaseService
from src.services.incident_service import IncidentRecord, IncidentService
from src.services.incident_evidence_service import IncidentEvidenceService

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
    CaseService.clear_cases()
    CaseHistoryService.clear_history()
    EvidenceService.clear_evidence()
    CustodyService.clear_custody()
    CaseSnapshotService.clear_snapshots()
    IncidentService.clear_incidents()
    IncidentEvidenceService.clear_evidence()


def setup_basic_mock_db(mock_db, mock_scope, mock_asset):
    scopes_list = mock_scope if isinstance(mock_scope, list) else [mock_scope]
    assets_list = mock_asset if isinstance(mock_asset, list) else [mock_asset]
    
    async def mock_get(model, ident):
        if model == Asset:
            for a in assets_list:
                if a.id == ident:
                    return a
            if len(assets_list) == 1:
                return assets_list[0]
        elif model == Scope:
            for s in scopes_list:
                if s.id == ident:
                    return s
            if len(scopes_list) == 1:
                return scopes_list[0]
        return None

    mock_db.get = AsyncMock(side_effect=mock_get)


# --- 1. Domain / Severity Registry Tests ---


def test_case_severity_registry() -> None:
    """Verify registry maps incident severities to case severity correctly based on max severity."""
    assert (
        CaseSeverityRegistry.calculate_severity([IncidentSeverity.CRITICAL])
        == CaseSeverity.CRITICAL
    )
    assert (
        CaseSeverityRegistry.calculate_severity(
            [IncidentSeverity.HIGH, IncidentSeverity.MEDIUM]
        )
        == CaseSeverity.HIGH
    )
    assert (
        CaseSeverityRegistry.calculate_severity(
            [IncidentSeverity.LOW, IncidentSeverity.MEDIUM]
        )
        == CaseSeverity.MEDIUM
    )
    assert (
        CaseSeverityRegistry.calculate_severity([IncidentSeverity.LOW])
        == CaseSeverity.LOW
    )
    assert CaseSeverityRegistry.calculate_severity([]) == CaseSeverity.LOW


# --- 2. Fingerprinting & Stability Tests ---


def test_case_fingerprint_stability() -> None:
    """Verify fingerprint remains stable across sorting of input list elements."""
    incidents = [uuid.uuid4(), uuid.uuid4()]
    alerts = [uuid.uuid4(), uuid.uuid4()]
    assets = [uuid.uuid4()]

    fp1 = CaseFingerprintService.generate_fingerprint(incidents, alerts, assets)
    # Reverse arrays to test sorting logic stability
    fp2 = CaseFingerprintService.generate_fingerprint(
        list(reversed(incidents)), list(reversed(alerts)), assets
    )
    assert fp1 == fp2


def test_case_fingerprint_stability_after_evidence_collection() -> None:
    """Verify that case fingerprint remains unchanged after adding evidence or transitioning state."""
    inc_ids = [uuid.uuid4()]
    alert_ids = [uuid.uuid4()]
    asset_ids = [uuid.uuid4()]

    fp_before = CaseFingerprintService.generate_fingerprint(
        inc_ids, alert_ids, asset_ids
    )

    case_id = uuid.uuid4()
    case = CaseRecord(
        case_id=case_id,
        case_fingerprint=fp_before,
        title="Stabil Test",
        description="Desc",
        severity=CaseSeverity.HIGH,
        status=CaseStatus.OPEN,
        incident_ids=inc_ids,
        alert_ids=alert_ids,
        asset_ids=asset_ids,
    )
    CaseService._cases[case_id] = case
    CaseService._fingerprint_lookup[fp_before] = case_id

    # Simulate evidence collection
    EvidenceService.add_evidence(
        case_id=case_id,
        source_entity="alert",
        source_id=alert_ids[0],
        collected_by=ADMIN_ID,
        raw_data="alert logs",
    )

    # Re-calculate fingerprint
    fp_after = CaseFingerprintService.generate_fingerprint(
        case.incident_ids, case.alert_ids, case.asset_ids
    )
    assert fp_before == fp_after


# --- 3. Case History Preservation Tests ---


def test_case_history_preserved_after_closure() -> None:
    """Verify that case history entries are immutable, append-only, and preserved after case closure."""
    case_id = uuid.uuid4()
    CaseHistoryService.record_event(case_id, "CREATED", "First event")
    CaseHistoryService.record_event(case_id, "ACTIVE", "Case active")

    # Transition to CLOSED should not touch prior log entries
    CaseHistoryService.record_event(case_id, "CLOSED", "Case closed")

    history = CaseHistoryService.get_history(case_id)
    assert len(history) == 3
    assert history[0].event_type == "CREATED"
    assert history[1].event_type == "ACTIVE"
    assert history[2].event_type == "CLOSED"


# --- 4. Evidence Integrity Tests ---


def test_evidence_integrity_verification() -> None:
    """Verify that evidence integrity checks successfully match hashes or detect tampered content."""
    case_id = uuid.uuid4()
    raw_data = "some log content"
    integrity_hash = (
        "d5ddcbd5eb85424149f97cab3d57f98298b3f38b789e9aaef3ed177c9f8e2406"
    )

    # Correct content
    record = EvidenceRecord(
        evidence_id=uuid.uuid4(),
        case_id=case_id,
        source_entity="logs",
        source_id=uuid.uuid4(),
        integrity_hash=integrity_hash,
        status=EvidenceStatus.COLLECTED,
        collected_by=ADMIN_ID,
        collected_at=datetime.now(timezone.utc),
        raw_data=raw_data,
    )

    assert EvidenceService.verify_integrity_check(record) is True

    # Tampered content
    record.raw_data = "tampered log content"
    assert EvidenceService.verify_integrity_check(record) is False


@pytest.mark.asyncio
async def test_evidence_integrity_failure_event(mock_db) -> None:
    """Verify that failed integrity verification emits the workflow event to trigger alert rules."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    record = EvidenceRecord(
        evidence_id=evidence_id,
        case_id=case_id,
        source_entity="host-logs",
        source_id=uuid.uuid4(),
        integrity_hash="invalidhash",
        status=EvidenceStatus.COLLECTED,
        collected_by=ADMIN_ID,
        collected_at=datetime.now(timezone.utc),
        raw_data="some log content",
    )
    EvidenceService._evidence[evidence_id] = record

    passed = await EvidenceService.verify_evidence_integrity(
        mock_db, evidence_id, ADMIN_ID
    )
    assert passed is False


def test_evidence_identity_preserved_after_verification() -> None:
    """Verify that evidence identity remains completely stable after transition to VERIFIED."""
    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    record = EvidenceRecord(
        evidence_id=evidence_id,
        case_id=case_id,
        source_entity="alert",
        source_id=uuid.uuid4(),
        integrity_hash="somehash",
        status=EvidenceStatus.COLLECTED,
        collected_by=ADMIN_ID,
        collected_at=datetime.now(timezone.utc),
        raw_data="logs",
    )
    EvidenceService._evidence[evidence_id] = record
    EvidenceService._fingerprint_lookup[
        EvidenceService.generate_fingerprint(
            record.source_entity, record.source_id, record.integrity_hash
        )
    ] = evidence_id

    # Verify transition
    EvidenceService.archive_evidence(evidence_id, ADMIN_ID)
    assert record.evidence_id == evidence_id
    assert record.status == EvidenceStatus.ARCHIVED


def test_evidence_fingerprint_stability_after_transfer() -> None:
    """Verify that evidence stable identity/fingerprint is preserved after transfer to another case."""
    case_id = uuid.uuid4()
    target_case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()

    record = EvidenceRecord(
        evidence_id=evidence_id,
        case_id=case_id,
        source_entity="alert",
        source_id=uuid.uuid4(),
        integrity_hash="somehash",
        status=EvidenceStatus.COLLECTED,
        collected_by=ADMIN_ID,
        collected_at=datetime.now(timezone.utc),
        raw_data="logs",
    )
    EvidenceService._evidence[evidence_id] = record
    fp_before = EvidenceService.generate_fingerprint(
        record.source_entity, record.source_id, record.integrity_hash
    )
    EvidenceService._fingerprint_lookup[fp_before] = evidence_id

    # Transfer
    EvidenceService.transfer_evidence(evidence_id, target_case_id, ADMIN_ID)

    fp_after = EvidenceService.generate_fingerprint(
        record.source_entity, record.source_id, record.integrity_hash
    )
    assert fp_before == fp_after
    assert record.case_id == target_case_id
    assert record.status == EvidenceStatus.TRANSFERRED


# --- 5. Chain of Custody Tests ---


def test_chain_of_custody_append_only() -> None:
    """Verify custody chain logging works in append-only style."""
    evidence_id = uuid.uuid4()
    CustodyService.record_custody_event(
        evidence_id, ChainOfCustodyAction.CREATED, ADMIN_ID, "Created", True
    )
    CustodyService.record_custody_event(
        evidence_id, ChainOfCustodyAction.ACCESSED, OPERATOR_ID, "Accessed", True
    )

    chain = CustodyService.get_custody(evidence_id)
    assert len(chain) == 2
    assert chain[0].action == ChainOfCustodyAction.CREATED
    assert chain[1].action == ChainOfCustodyAction.ACCESSED


def test_chain_of_custody_preserved_after_case_closure() -> None:
    """Verify that custody timelines are retained after case closure."""
    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()

    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="Case closed test",
        description="Desc",
        severity=CaseSeverity.LOW,
        status=CaseStatus.OPEN,
    )
    CaseService._cases[case_id] = case

    CustodyService.record_custody_event(
        evidence_id, ChainOfCustodyAction.CREATED, ADMIN_ID, "Created", True
    )

    # Close case
    case.status = CaseStatus.CLOSED

    # Verify custody remains accessible
    chain = CustodyService.get_custody(evidence_id)
    assert len(chain) == 1
    assert chain[0].notes == "Created"


# --- 6. Terminal State Enforcement Tests ---


def test_archived_evidence_terminal_enforcement() -> None:
    """Verify ARCHIVED terminal state for evidence blocks modification, transfers, or reassignment."""
    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    record = EvidenceRecord(
        evidence_id=evidence_id,
        case_id=case_id,
        source_entity="alert",
        source_id=uuid.uuid4(),
        integrity_hash="somehash",
        status=EvidenceStatus.ARCHIVED,
        collected_by=ADMIN_ID,
        collected_at=datetime.now(timezone.utc),
        raw_data="logs",
    )
    EvidenceService._evidence[evidence_id] = record
    EvidenceService._fingerprint_lookup[
        EvidenceService.generate_fingerprint(
            record.source_entity, record.source_id, record.integrity_hash
        )
    ] = evidence_id

    # Test modification / transfer block
    with pytest.raises(ValueError, match="is ARCHIVED and cannot be transferred"):
        EvidenceService.transfer_evidence(evidence_id, uuid.uuid4(), ADMIN_ID)

    # Test collection block (recollection)
    with pytest.raises(ValueError, match="is ARCHIVED and cannot be modified or recollected"):
        EvidenceService.add_evidence(
            case_id=case_id,
            source_entity=record.source_entity,
            source_id=record.source_id,
            collected_by=ADMIN_ID,
            raw_data="logs",
            integrity_hash=record.integrity_hash,
        )


def test_case_closed_terminal_enforcement() -> None:
    """Verify CLOSED state is terminal for cases and blocks transitions or edits."""
    case_id = uuid.uuid4()
    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="Closed Case",
        description="Desc",
        severity=CaseSeverity.LOW,
        status=CaseStatus.CLOSED,
    )
    CaseService._cases[case_id] = case

    with pytest.raises(ValueError, match="Case is CLOSED and cannot be mutated or reopened"):
        CaseService.validate_transition(case.status, CaseStatus.ACTIVE)

    mock_db = MagicMock()
    with pytest.raises(ValueError, match="Case is CLOSED and cannot be modified"):
        # Run assignment check
        import asyncio
        asyncio.run(CaseService.assign_case(mock_db, case_id, ADMIN_ID))


# --- 7. Snapshot Cache Rebuild Tests ---


def test_case_snapshot_rebuild_consistency() -> None:
    """Verify that case snapshot rebuilds statistics dynamically from in-memory cases."""
    case_id = uuid.uuid4()
    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="Snapshot Case",
        description="Desc",
        severity=CaseSeverity.CRITICAL,
        status=CaseStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    CaseService._cases[case_id] = case

    snapshot = CaseSnapshotService.get_snapshot(ASSET_ID)
    assert snapshot["total"] == 1
    assert snapshot["critical"] == 1
    assert snapshot["open"] == 1

    # Invalidate and check dynamic rebuild
    CaseSnapshotService.invalidate_cache()
    snapshot_rebuilt = CaseSnapshotService.get_snapshot(ASSET_ID)
    assert snapshot_rebuilt["total"] == 1


# --- 8. AI Copilot Integration Tests ---


@pytest.mark.asyncio
async def test_ai_context_case_injection(mock_db) -> None:
    """Verify case summary and timeline contexts inject into AI prompt context builders."""
    from src.services.asset_report_service import AssetReportService

    original_generate = AssetReportService.generate_asset_report
    AssetReportService.generate_asset_report = AsyncMock(
        return_value={
            "asset": {"id": str(ASSET_ID)},
            "ports": [],
            "services": [],
            "technologies": [],
            "risk": {},
            "findings": [],
            "exposure": {},
        }
    )

    try:
        case_id = uuid.uuid4()
        case = CaseRecord(
            case_id=case_id,
            case_fingerprint="fp",
            title="AI Case",
            description="Desc",
            severity=CaseSeverity.MEDIUM,
            status=CaseStatus.OPEN,
            asset_ids=[ASSET_ID],
        )
        CaseService._cases[case_id] = case

        context = await AIContextBuilder.build_asset_context(mock_db, ASSET_ID)
        assert "case_summary" in context
        assert "active_cases" in context
        assert context["case_summary"]["total"] == 1
    finally:
        AssetReportService.generate_asset_report = original_generate


# --- 9. RBAC Scope Validation Tests ---


@pytest.mark.asyncio
async def test_rbac_case_scope_validation(mock_db, mock_scope, mock_asset, mock_operator) -> None:
    """Verify that operators are rejected when querying or modifying cases with assets outside scope."""
    other_scope = Scope()
    other_scope.id = uuid.uuid4()
    other_scope.owner_id = uuid.uuid4()
    
    other_asset = Asset()
    other_asset.id = uuid.uuid4()
    other_asset.scope_id = other_scope.id
    other_asset.deleted_at = None

    setup_basic_mock_db(mock_db, [mock_scope, other_scope], [mock_asset, other_asset])

    case_id = uuid.uuid4()
    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="Scope Block Case",
        description="Desc",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
        asset_ids=[other_asset.id],  # Asset outside operator's scope
    )
    CaseService._cases[case_id] = case

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        from src.api.v1.routers.cases import check_case_ownership
        await check_case_ownership(mock_db, case, mock_operator)

    assert exc_info.value.status_code == 403


# --- 10. Auto-Creation & Deduplication Tests ---


@pytest.mark.asyncio
async def test_case_auto_creation(mock_db, mock_scope, mock_asset) -> None:
    """Verify sync_cases aggregates non-closed incidents and auto-creates cases correctly."""
    setup_basic_mock_db(mock_db, mock_scope, mock_asset)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    # Seed incident
    inc_id = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=inc_id,
        incident_fingerprint="inc-fp",
        title="Test Incident",
        description="Detail",
        severity=IncidentSeverity.CRITICAL,
        status=IncidentStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[inc_id] = inc

    # Run case sync
    await CaseService.sync_cases(mock_db)

    cases = CaseService.get_all_cases()
    assert len(cases) == 1
    assert cases[0].severity == CaseSeverity.CRITICAL
    assert inc_id in cases[0].incident_ids


@pytest.mark.asyncio
async def test_case_sync_preserves_identity(mock_db, mock_scope, mock_asset) -> None:
    """Verify Case sync does not create duplicate cases if fingerprints match."""
    setup_basic_mock_db(mock_db, mock_scope, mock_asset)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    inc_id = uuid.uuid4()
    inc = IncidentRecord(
        incident_id=inc_id,
        incident_fingerprint="inc-fp",
        title="Test Incident",
        description="Detail",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    IncidentService._incidents[inc_id] = inc

    # Sync first time
    await CaseService.sync_cases(mock_db)
    cases_1 = CaseService.get_all_cases()
    assert len(cases_1) == 1
    case_id_1 = cases_1[0].case_id

    # Sync second time
    await CaseService.sync_cases(mock_db)
    cases_2 = CaseService.get_all_cases()
    assert len(cases_2) == 1
    assert cases_2[0].case_id == case_id_1


@pytest.mark.asyncio
async def test_case_identity_preserved_after_escalation(mock_db, mock_scope, mock_asset) -> None:
    """Verify Case ID remains stable after transition to ESCALATED and back to ACTIVE."""
    setup_basic_mock_db(mock_db, mock_scope, mock_asset)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    case_id = uuid.uuid4()
    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="Escalation Case",
        description="Desc",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    CaseService._cases[case_id] = case

    # OPEN -> ACTIVE
    await CaseService.transition_status(mock_db, case_id, CaseStatus.ACTIVE)
    assert case.status == CaseStatus.ACTIVE

    # ACTIVE -> ESCALATED
    await CaseService.transition_status(mock_db, case_id, CaseStatus.ESCALATED)
    assert case.status == CaseStatus.ESCALATED
    assert case.case_id == case_id

    # ESCALATED -> ACTIVE
    await CaseService.transition_status(mock_db, case_id, CaseStatus.ACTIVE)
    assert case.status == CaseStatus.ACTIVE
    assert case.case_id == case_id


# --- 11. REST API Routing Endpoints Tests ---


@pytest.mark.asyncio
async def test_api_list_cases(client, mock_admin, mock_db) -> None:
    """Verify that API GET /cases lists all cases."""
    case_id = uuid.uuid4()
    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="API Case",
        description="Desc",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    CaseService._cases[case_id] = case

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.get("/api/v1/cases", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["case_id"] == str(case_id)


@pytest.mark.asyncio
async def test_api_get_case(client, mock_admin, mock_db) -> None:
    """Verify API GET /cases/{id} retrieves detail."""
    case_id = uuid.uuid4()
    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="API Case",
        description="Desc",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    CaseService._cases[case_id] = case

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["title"] == "API Case"


@pytest.mark.asyncio
async def test_api_assign_case(client, mock_admin, mock_db) -> None:
    """Verify API assignment updates case owner."""
    case_id = uuid.uuid4()
    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="API Case",
        description="Desc",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    CaseService._cases[case_id] = case
    mock_db.commit = AsyncMock()

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.post(
        f"/api/v1/cases/{case_id}/assign",
        json={"owner_id": str(OPERATOR_ID)},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["owner"] == str(OPERATOR_ID)


@pytest.mark.asyncio
async def test_api_lifecycle_transitions(client, mock_admin, mock_db) -> None:
    """Verify API lifecycle endpoints successfully transition case states."""
    case_id = uuid.uuid4()
    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="API Case",
        description="Desc",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    CaseService._cases[case_id] = case
    mock_db.commit = AsyncMock()

    headers = get_auth_header(ADMIN_ID, "admin")

    # activate
    res = await client.post(f"/api/v1/cases/{case_id}/activate", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "ACTIVE"

    # review
    res = await client.post(f"/api/v1/cases/{case_id}/review", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "UNDER_REVIEW"

    # resolve
    res = await client.post(f"/api/v1/cases/{case_id}/resolve", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "RESOLVED"

    # close
    res = await client.post(f"/api/v1/cases/{case_id}/close", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_api_evidence_endpoints(client, mock_admin, mock_db) -> None:
    """Verify POST /cases/{id}/evidence and GET /cases/{id}/evidence collect and retrieve records."""
    case_id = uuid.uuid4()
    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="API Case",
        description="Desc",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    CaseService._cases[case_id] = case
    mock_db.commit = AsyncMock()

    headers = get_auth_header(ADMIN_ID, "admin")

    # Collect
    res = await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        json={
            "source_entity": "alert",
            "source_id": str(uuid.uuid4()),
            "raw_data": "log alert data details",
        },
        headers=headers,
    )
    assert res.status_code == 200
    evidence_id = res.json()["evidence_id"]

    # List
    res_list = await client.get(f"/api/v1/cases/{case_id}/evidence", headers=headers)
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1
    assert res_list.json()[0]["evidence_id"] == evidence_id


@pytest.mark.asyncio
async def test_api_custody_timeline(client, mock_admin, mock_db) -> None:
    """Verify GET /cases/{id}/custody retrieves sorted chain of custody timeline."""
    case_id = uuid.uuid4()
    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="API Case",
        description="Desc",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    CaseService._cases[case_id] = case
    mock_db.commit = AsyncMock()

    headers = get_auth_header(ADMIN_ID, "admin")

    # Collect evidence to generate first custody entry
    await client.post(
        f"/api/v1/cases/{case_id}/evidence",
        json={
            "source_entity": "logs",
            "source_id": str(uuid.uuid4()),
            "raw_data": "logs content",
        },
        headers=headers,
    )

    res = await client.get(f"/api/v1/cases/{case_id}/custody", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["action"] == "COLLECTED"


@pytest.mark.asyncio
async def test_api_transfer_evidence(client, mock_admin, mock_db) -> None:
    """Verify POST /cases/{id}/transfer moves evidence case link."""
    case_id = uuid.uuid4()
    target_case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()

    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp1",
        title="Source Case",
        description="Desc",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    CaseService._cases[case_id] = case

    target_case = CaseRecord(
        case_id=target_case_id,
        case_fingerprint="fp2",
        title="Target Case",
        description="Desc",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    CaseService._cases[target_case_id] = target_case

    record = EvidenceRecord(
        evidence_id=evidence_id,
        case_id=case_id,
        source_entity="alert",
        source_id=uuid.uuid4(),
        integrity_hash="hash",
        status=EvidenceStatus.COLLECTED,
        collected_by=ADMIN_ID,
        collected_at=datetime.now(timezone.utc),
        raw_data="logs",
    )
    EvidenceService._evidence[evidence_id] = record

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.post(
        f"/api/v1/cases/{case_id}/transfer",
        json={"evidence_id": str(evidence_id), "new_case_id": str(target_case_id), "notes": "Moving"},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["case_id"] == str(target_case_id)
    assert res.json()["status"] == "TRANSFERRED"


@pytest.mark.asyncio
async def test_api_timeline(client, mock_admin, mock_db) -> None:
    """Verify GET /cases/{id}/timeline retrieves history audit logs."""
    case_id = uuid.uuid4()
    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="API Case",
        description="Desc",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    CaseService._cases[case_id] = case
    CaseHistoryService.record_event(case_id, "CREATED", "Seed creation")

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.get(f"/api/v1/cases/{case_id}/timeline", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["event_type"] == "CREATED"


@pytest.mark.asyncio
async def test_api_verify_integrity_endpoint(client, mock_admin, mock_db) -> None:
    """Verify POST /cases/{id}/evidence/{evidence_id}/verify checks forensic hash validity."""
    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()

    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="API Case",
        description="Desc",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    CaseService._cases[case_id] = case

    raw_data = "log logs logs"
    import hashlib
    h = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()

    record = EvidenceRecord(
        evidence_id=evidence_id,
        case_id=case_id,
        source_entity="logs",
        source_id=uuid.uuid4(),
        integrity_hash=h,
        status=EvidenceStatus.COLLECTED,
        collected_by=ADMIN_ID,
        collected_at=datetime.now(timezone.utc),
        raw_data=raw_data,
    )
    EvidenceService._evidence[evidence_id] = record

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/verify",
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["integrity_verified"] is True


@pytest.mark.asyncio
async def test_api_archive_evidence(client, mock_admin, mock_db) -> None:
    """Verify POST /cases/{id}/evidence/{evidence_id}/archive locks evidence state."""
    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()

    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="API Case",
        description="Desc",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    CaseService._cases[case_id] = case

    record = EvidenceRecord(
        evidence_id=evidence_id,
        case_id=case_id,
        source_entity="logs",
        source_id=uuid.uuid4(),
        integrity_hash="hash",
        status=EvidenceStatus.COLLECTED,
        collected_by=ADMIN_ID,
        collected_at=datetime.now(timezone.utc),
        raw_data="logs",
    )
    EvidenceService._evidence[evidence_id] = record

    headers = get_auth_header(ADMIN_ID, "admin")
    res = await client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/archive",
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ARCHIVED"


@pytest.mark.asyncio
async def test_api_rbac_restrictions(client, mock_operator, mock_db) -> None:
    """Verify operators without matching asset scopes are blocked from mutating operations."""
    case_id = uuid.uuid4()
    case = CaseRecord(
        case_id=case_id,
        case_fingerprint="fp",
        title="Restricted Case",
        description="Desc",
        severity=CaseSeverity.MEDIUM,
        status=CaseStatus.OPEN,
        asset_ids=[ASSET_ID],
    )
    CaseService._cases[case_id] = case

    from src.infrastructure.database.models import Scope, Asset
    bad_scope = Scope()
    bad_scope.id = SCOPE_ID
    bad_scope.owner_id = uuid.uuid4()  # Not owned by operator!
    bad_scope.deleted_at = None

    mock_asset_obj = Asset()
    mock_asset_obj.id = ASSET_ID
    mock_asset_obj.scope_id = SCOPE_ID
    mock_asset_obj.deleted_at = None

    mock_db.get = AsyncMock(
        side_effect=lambda model, ident: (
            mock_asset_obj
            if model == Asset
            else (bad_scope if model == Scope else None)
        )
    )

    headers = get_auth_header(OPERATOR_ID, "operator")
    res = await client.post(f"/api/v1/cases/{case_id}/activate", headers=headers)
    assert res.status_code == 403


def test_case_severity_registry_invalid() -> None:
    """Verify registry handles invalid string severities gracefully."""
    assert CaseSeverityRegistry.calculate_severity(["INVALID", "LOW"]) == CaseSeverity.LOW


def test_case_history_clear() -> None:
    """Verify case history can be cleared."""
    CaseHistoryService.record_event(uuid.uuid4(), "CREATED", "First event")
    CaseHistoryService.clear_history()
    assert CaseHistoryService._history == {}


def test_evidence_clear() -> None:
    """Verify evidence store can be cleared."""
    case_id = uuid.uuid4()
    EvidenceService.add_evidence(case_id, "logs", uuid.uuid4(), ADMIN_ID, "data")
    EvidenceService.clear_evidence()
    assert EvidenceService.get_all_evidence() == []


def test_custody_clear() -> None:
    """Verify custody timeline can be cleared."""
    evidence_id = uuid.uuid4()
    CustodyService.record_custody_event(
        evidence_id, ChainOfCustodyAction.CREATED, ADMIN_ID, "Notes", True
    )
    CustodyService.clear_custody()
    assert CustodyService.get_custody(evidence_id) == []


def test_case_service_clear() -> None:
    """Verify cases store can be cleared."""
    case_id = uuid.uuid4()
    CaseService._cases[case_id] = CaseRecord(
        case_id, "fp", "title", "desc", CaseSeverity.LOW, CaseStatus.OPEN
    )
    CaseService.clear_cases()
    assert CaseService.get_all_cases() == []


def test_case_evidence_correlation() -> None:
    """Verify correlation correctly maps case-specific and incident-specific evidence."""
    case_id = uuid.uuid4()
    inc_id = uuid.uuid4()

    # Add case-specific evidence
    ev = EvidenceService.add_evidence(
        case_id, "logs", uuid.uuid4(), ADMIN_ID, "logs content"
    )

    # Add incident evidence reference
    class DummyAlert:
        def __init__(self, alert_id):
            self.alert_id = alert_id

    alert = DummyAlert(uuid.uuid4())
    IncidentEvidenceService.add_evidence(inc_id, "alerts", alert)

    correlated = CaseEvidenceCorrelationService.get_correlated_evidence(
        case_id, [inc_id]
    )
    assert len(correlated["case_evidence"]) == 1
    assert correlated["case_evidence"][0].evidence_id == ev.evidence_id
    assert len(correlated["incident_evidence"][str(inc_id)]["alerts"]) == 1


def test_case_snapshot_global() -> None:
    """Verify that case snapshot rebuilds global statistics correctly."""
    case_id = uuid.uuid4()
    CaseService._cases[case_id] = CaseRecord(
        case_id, "fp", "title", "desc", CaseSeverity.MEDIUM, CaseStatus.OPEN
    )

    CaseSnapshotService.invalidate_cache()
    global_snap = CaseSnapshotService.get_snapshot()
    assert global_snap["total"] == 1
    assert global_snap["open"] == 1
    assert global_snap["medium"] == 1

