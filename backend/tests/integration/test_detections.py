import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.core.security import create_access_token
from src.domain.entities.detection import (
    CoverageStatus,
    DetectionSeverity,
    DetectionStatus,
)
from src.infrastructure.database.models import Scope, User
from src.services.ai_context_builder import AIContextBuilder
from src.services.attack_registry import AttackRegistry
from src.services.detection_coverage_service import DetectionCoverageService
from src.services.detection_drift_service import DetectionDriftService
from src.services.detection_fingerprint_service import DetectionFingerprintService
from src.services.detection_gap_service import DetectionGapService
from src.services.detection_history_service import DetectionHistoryService
from src.services.detection_severity_registry import DetectionSeverityRegistry
from src.services.detection_snapshot_service import DetectionSnapshotService
from src.services.detection_service import DetectionRecord, DetectionService
from src.services.workflow_event_service import WorkflowEventService

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
    s.owner_id = uuid.uuid4()  # Owned by someone else
    s.name = "Other Scope"
    s.deleted_at = None
    return s


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_stores():
    DetectionService.clear_detections()
    DetectionHistoryService.clear_history()
    DetectionSnapshotService.clear_snapshots()


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


def setup_basic_mock_db(mock_db, mock_scope, mock_scope_2=None):
    async def mock_get(model, ident):
        if model == Scope:
            if ident == mock_scope.id:
                return mock_scope
            if mock_scope_2 and ident == mock_scope_2.id:
                return mock_scope_2
        return None

    mock_db.get = AsyncMock(side_effect=mock_get)

    async def mock_execute(query):
        mock_result = MagicMock()
        scopes = [mock_scope]
        if mock_scope_2:
            scopes.append(mock_scope_2)

        query_str = str(query).lower()
        if "from scope" not in query_str:
            mock_result.scalars().all.return_value = []
            mock_result.scalar_one_or_none.return_value = None
            return mock_result

        owner_id_val = None
        scope_id_val = None
        try:
            params = query.compile().params
            for k, v in params.items():
                if isinstance(v, uuid.UUID) or (isinstance(v, str) and len(v) == 36):
                    val = uuid.UUID(str(v))
                    if val == mock_scope.id or (mock_scope_2 and val == mock_scope_2.id):
                        scope_id_val = val
                    else:
                        owner_id_val = val
        except Exception:
            pass

        filtered_scopes = scopes
        if scope_id_val:
            filtered_scopes = [s for s in scopes if s.id == scope_id_val]
        elif owner_id_val:
            filtered_scopes = [s for s in scopes if s.owner_id == owner_id_val]

        if filtered_scopes:
            mock_result.scalar_one_or_none.return_value = filtered_scopes[0]
            mock_result.scalars().all.return_value = filtered_scopes
        else:
            mock_result.scalar_one_or_none.return_value = None
            mock_result.scalars().all.return_value = []

        return mock_result

    mock_db.execute = AsyncMock(side_effect=mock_execute)


# --- 1. Domain / Severity Registry Tests ---


def test_detection_severity_registry() -> None:
    """Verify registry resolves and maps severities correctly."""
    assert DetectionSeverityRegistry.resolve_severity("CRITICAL") == DetectionSeverity.CRITICAL
    assert DetectionSeverityRegistry.resolve_severity("high") == DetectionSeverity.HIGH
    assert DetectionSeverityRegistry.resolve_severity("INVALID") == DetectionSeverity.LOW

    highest = DetectionSeverityRegistry.get_highest_severity(["LOW", "MEDIUM", "HIGH"])
    assert highest == DetectionSeverity.HIGH

    highest_critical = DetectionSeverityRegistry.get_highest_severity([DetectionSeverity.CRITICAL, "LOW"])
    assert highest_critical == DetectionSeverity.CRITICAL


# --- 2. Fingerprinting & Stability Tests ---


def test_detection_fingerprint_stability() -> None:
    """Verify detection fingerprint remains stable regardless of technique ordering or whitespace."""
    fp1 = DetectionFingerprintService.generate_fingerprint("  Rule A  ", ["T1059", "T1562"])
    fp2 = DetectionFingerprintService.generate_fingerprint("Rule A", ["T1562", "T1059"])
    assert fp1 == fp2


def test_detection_fingerprint_stability_rule() -> None:
    """Verify fingerprint only changes when name or techniques change, remaining stable across status transitions."""
    name = "Stable Rule"
    techs = ["T1078"]
    fp_before = DetectionFingerprintService.generate_fingerprint(name, techs)

    record = DetectionService.create_or_sync_detection(name, "Desc", "HIGH", techs)
    assert record.detection_fingerprint == fp_before

    # Disable detection
    disabled = DetectionService.disable_detection(record.detection_id)
    assert disabled.detection_fingerprint == fp_before

    # Sync again
    synced = DetectionService.create_or_sync_detection(name, "New Desc", "CRITICAL", techs)
    assert synced.detection_fingerprint == fp_before
    assert synced.status == DetectionStatus.DISABLED  # Terminal status preserved


# --- 3. Core Services & Sync Tests ---


def test_detection_auto_creation() -> None:
    """Verify syncing a new detection creates a new ACTIVE record and logs CREATED to history."""
    name = "Auto Rule"
    desc = "Auto created rule description"
    techs = ["T1027"]

    record = DetectionService.create_or_sync_detection(name, desc, "MEDIUM", techs, SCOPE_ID)
    assert record.detection_id is not None
    assert record.name == name
    assert record.status == DetectionStatus.ACTIVE
    assert record.scope_id == SCOPE_ID

    history = DetectionHistoryService.get_history(record.detection_id)
    assert len(history) == 1
    assert history[0].event_type == "CREATED"


def test_detection_sync_preserves_identity() -> None:
    """Verify sync on same fingerprint preserves detection_id, fingerprint, history, and creation timestamp."""
    name = "Identity Rule"
    techs = ["T1105"]

    first = DetectionService.create_or_sync_detection(name, "First desc", "LOW", techs)
    first_id = first.detection_id
    first_created = first.created_at

    second = DetectionService.create_or_sync_detection(name, "Second desc", "HIGH", techs)
    assert second.detection_id == first_id
    assert second.created_at == first_created
    assert second.description == "Second desc"
    assert second.severity == DetectionSeverity.HIGH


def test_detection_history_preserved() -> None:
    """Verify history entries are immutable and appended correctly."""
    record = DetectionService.create_or_sync_detection("History Test", "Desc", "LOW", ["T1047"])
    det_id = record.detection_id

    DetectionService.create_or_sync_detection("History Test", "New Desc", "HIGH", ["T1047"])
    DetectionService.disable_detection(det_id)

    history = DetectionHistoryService.get_history(det_id)
    assert len(history) == 3
    assert history[0].event_type == "CREATED"
    assert history[1].event_type == "UPDATED"
    assert history[2].event_type == "DISABLED"


def test_detection_disable_transition() -> None:
    """Verify disable transitions state to DISABLED (terminal status)."""
    record = DetectionService.create_or_sync_detection("Disable Test", "Desc", "LOW", ["T1055"])
    assert record.status == DetectionStatus.ACTIVE

    disabled = DetectionService.disable_detection(record.detection_id)
    assert disabled.status == DetectionStatus.DISABLED

    # Repeat disable does not duplicate logs/fail
    disabled_again = DetectionService.disable_detection(record.detection_id)
    assert disabled_again.status == DetectionStatus.DISABLED


def test_detection_deprecate_transition() -> None:
    """Verify deprecate transitions state to DEPRECATED (terminal status)."""
    record = DetectionService.create_or_sync_detection("Deprecate Test", "Desc", "LOW", ["T1055"])
    assert record.status == DetectionStatus.ACTIVE

    deprecated = DetectionService.deprecate_detection(record.detection_id)
    assert deprecated.status == DetectionStatus.DEPRECATED


def test_detection_identity_preserved_after_disable() -> None:
    """Verify sync run producing the same fingerprint does not reactivate a DISABLED detection."""
    record = DetectionService.create_or_sync_detection("Term Rule", "Desc", "LOW", ["T1059"])
    DetectionService.disable_detection(record.detection_id)

    synced = DetectionService.create_or_sync_detection("Term Rule", "Desc", "LOW", ["T1059"])
    assert synced.status == DetectionStatus.DISABLED


def test_detection_identity_preserved_after_deprecation() -> None:
    """Verify sync run producing the same fingerprint does not reactivate a DEPRECATED detection."""
    record = DetectionService.create_or_sync_detection("Term Rule 2", "Desc", "LOW", ["T1059"])
    DetectionService.deprecate_detection(record.detection_id)

    synced = DetectionService.create_or_sync_detection("Term Rule 2", "Desc", "LOW", ["T1059"])
    assert synced.status == DetectionStatus.DEPRECATED


def test_attack_mapping_change_detection() -> None:
    """Verify changing mapping appends ATTACK_MAPPING_CHANGED and updates techniques/fingerprint without deleting history."""
    record = DetectionService.create_or_sync_detection("Mapping Rule", "Desc", "LOW", ["T1059"])
    det_id = record.detection_id
    fp_before = record.detection_fingerprint

    updated = DetectionService.update_detection_mapping(det_id, ["T1059", "T1562"])
    assert updated.attack_techniques == ["T1059", "T1562"]
    assert updated.detection_fingerprint != fp_before

    history = DetectionHistoryService.get_history(det_id)
    assert any(h.event_type == "ATTACK_MAPPING_CHANGED" for h in history)


# --- 4. Coverage, Gaps & Drift Tests ---


def test_coverage_score_calculation() -> None:
    """Verify coverage score calculations: covered techniques / total pre-seeded techniques."""
    total_techs = len(AttackRegistry.get_registered_techniques())
    assert total_techs > 0

    # No detections -> 0% coverage
    score_empty = DetectionCoverageService.calculate_overall_score()
    assert score_empty == 0.0

    # Add detection mapping to 1 technique -> 1/total coverage score
    DetectionService.create_or_sync_detection("Rule A", "Desc", "LOW", ["T1059"])
    score_1 = DetectionCoverageService.calculate_overall_score()
    assert score_1 == 1 / total_techs


def test_uncovered_techniques_detection() -> None:
    """Verify uncovered techniques are flagged as NOT_COVERED."""
    registered = AttackRegistry.get_registered_techniques()
    DetectionService.create_or_sync_detection("Rule A", "Desc", "LOW", ["T1059"])

    coverage = DetectionCoverageService.calculate_coverage()
    uncovered = [c for c in coverage if c.coverage_status == CoverageStatus.NOT_COVERED]
    assert len(uncovered) == len(registered) - 1
    assert all(u.technique_id != "T1059" for u in uncovered)


@pytest.mark.asyncio
async def test_detection_gap_detection(mock_db) -> None:
    """Verify DetectionGapService detects gaps and emits detection.gap_detected events."""
    setup_basic_mock_db(mock_db, Scope())

    # Mock WorkflowEventService.emit_event
    WorkflowEventService.emit_event = AsyncMock()

    await DetectionGapService.check_gaps_and_regressions(mock_db)

    # Since all techniques are uncovered initially, it should emit gap_detected for all pre-seeded techniques
    assert WorkflowEventService.emit_event.call_count == len(AttackRegistry.get_registered_techniques())
    assert WorkflowEventService.emit_event.call_args_list[0][1]["event_type"] == "detection.gap_detected"


@pytest.mark.asyncio
async def test_detection_coverage_regression(mock_db) -> None:
    """Verify disabling a detection causes a technique status regression, emitting detection.coverage_regressed."""
    setup_basic_mock_db(mock_db, Scope())

    # Create detection & generate baseline snapshot
    record = DetectionService.create_or_sync_detection("Regress Rule", "Desc", "LOW", ["T1059"])
    DetectionSnapshotService.generate_snapshot()

    # Disable detection (causes regression on T1059 from COVERED -> PARTIALLY_COVERED)
    DetectionService.disable_detection(record.detection_id)

    WorkflowEventService.emit_event = AsyncMock()
    await DetectionGapService.check_gaps_and_regressions(mock_db)

    # Check for regression event
    regression_calls = [
        call for call in WorkflowEventService.emit_event.call_args_list
        if call[1]["event_type"] == "detection.coverage_regressed"
    ]
    assert len(regression_calls) > 0


@pytest.mark.asyncio
async def test_detection_drift_detection(mock_db) -> None:
    """Verify that score changes or mapping changes trigger detection.drift events."""
    setup_basic_mock_db(mock_db, Scope())

    DetectionService.create_or_sync_detection("Drift Rule", "Desc", "LOW", ["T1059"])
    DetectionSnapshotService.generate_snapshot()

    # Remove the technique mapping (causes score decrease)
    DetectionService.update_detection_mapping(
        DetectionService.get_all_detections()[0].detection_id, []
    )

    WorkflowEventService.emit_event = AsyncMock()
    await DetectionDriftService.check_drift(mock_db)

    drift_calls = [
        call for call in WorkflowEventService.emit_event.call_args_list
        if call[1]["event_type"] == "detection.drift"
    ]
    assert len(drift_calls) > 0


def test_snapshot_rebuild_consistency() -> None:
    """Verify cache-only snapshot rebuild consistency when snapshot is missing or cleared."""
    DetectionService.create_or_sync_detection("Snap Rule", "Desc", "LOW", ["T1059"])

    snapshot = DetectionSnapshotService.get_snapshot()
    assert snapshot["coverage_score"] > 0.0

    # Clear snapshot cache
    DetectionSnapshotService.clear_snapshots()
    assert len(DetectionSnapshotService._snapshots) == 0

    # get_snapshot should rebuild it dynamically
    snapshot_rebuilt = DetectionSnapshotService.get_snapshot()
    assert snapshot_rebuilt["coverage_score"] == snapshot["coverage_score"]
    assert len(DetectionSnapshotService._snapshots) == 1


# --- 5. API Gateway / Integration Tests ---


@pytest.mark.asyncio
async def test_api_post_detections(client, mock_db) -> None:
    """Verify creating a detection rule via API."""
    scope = Scope()
    scope.id = SCOPE_ID
    scope.owner_id = OPERATOR_ID
    scope.deleted_at = None
    setup_basic_mock_db(mock_db, scope)

    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {
        "name": "API Rule",
        "description": "API Description",
        "severity": "HIGH",
        "attack_techniques": ["T1059", "T1562"],
        "scope_id": str(SCOPE_ID),
    }

    res = await client.post("/api/v1/detections", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "API Rule"
    assert data["severity"] == "HIGH"
    assert data["attack_techniques"] == ["T1059", "T1562"]


@pytest.mark.asyncio
async def test_api_get_detections(client, mock_db) -> None:
    """Verify retrieving detection rules with scope checks."""
    scope = Scope()
    scope.id = SCOPE_ID
    scope.owner_id = OPERATOR_ID
    scope.deleted_at = None
    setup_basic_mock_db(mock_db, scope)

    # Seed detections
    DetectionService.create_or_sync_detection("Scoped Rule", "Desc", "LOW", ["T1059"], SCOPE_ID)
    DetectionService.create_or_sync_detection("Global Rule", "Desc", "LOW", ["T1562"])

    # Reader retrieves (should only see owned scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    res = await client.get("/api/v1/detections", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "Scoped Rule"

    # Admin retrieves (sees all)
    admin_headers = get_auth_header(ADMIN_ID, "admin")
    res_admin = await client.get("/api/v1/detections", headers=admin_headers)
    assert res_admin.status_code == 200
    data_admin = res_admin.json()
    assert len(data_admin) == 2


@pytest.mark.asyncio
async def test_api_disable_deprecate_detections(client, mock_db) -> None:
    """Verify mutating status via disable/deprecate endpoints."""
    scope = Scope()
    scope.id = SCOPE_ID
    scope.owner_id = OPERATOR_ID
    scope.deleted_at = None
    setup_basic_mock_db(mock_db, scope)

    record = DetectionService.create_or_sync_detection("Mutate Rule", "Desc", "LOW", ["T1059"], SCOPE_ID)

    headers = get_auth_header(OPERATOR_ID, "operator")

    # Disable
    res_disable = await client.post(f"/api/v1/detections/{record.detection_id}/disable", headers=headers)
    assert res_disable.status_code == 200
    assert res_disable.json()["status"] == "DISABLED"

    # Deprecate
    res_deprecate = await client.post(f"/api/v1/detections/{record.detection_id}/deprecate", headers=headers)
    assert res_deprecate.status_code == 200
    assert res_deprecate.json()["status"] == "DEPRECATED"


@pytest.mark.asyncio
async def test_api_coverage_gaps_summary(client, mock_db) -> None:
    """Verify coverage, gaps, and summary endpoints."""
    scope = Scope()
    scope.id = SCOPE_ID
    scope.owner_id = OPERATOR_ID
    scope.deleted_at = None
    setup_basic_mock_db(mock_db, scope)

    DetectionService.create_or_sync_detection("Mutate Rule", "Desc", "LOW", ["T1059"], SCOPE_ID)

    headers = get_auth_header(OPERATOR_ID, "operator")

    # Coverage
    res_cov = await client.get(f"/api/v1/detections/coverage?scope_id={SCOPE_ID}", headers=headers)
    assert res_cov.status_code == 200
    assert len(res_cov.json()) == len(AttackRegistry.get_registered_techniques())

    # Gaps
    res_gaps = await client.get(f"/api/v1/detections/gaps?scope_id={SCOPE_ID}", headers=headers)
    assert res_gaps.status_code == 200
    assert len(res_gaps.json()) == len(AttackRegistry.get_registered_techniques()) - 1

    # Summary
    res_sum = await client.get(f"/api/v1/detections/summary?scope_id={SCOPE_ID}", headers=headers)
    assert res_sum.status_code == 200
    assert res_sum.json()["total_detections"] == 1


# --- 6. AI Context Builder Tests ---


@pytest.mark.asyncio
async def test_ai_context_detection_injection(mock_db) -> None:
    """Verify that AIContextBuilder injects detection coverage, gaps, score, and summary data."""
    setup_basic_mock_db(mock_db, Scope())

    DetectionService.create_or_sync_detection("AI Rule", "Desc", "LOW", ["T1059"])

    context = await AIContextBuilder.build_executive_context(mock_db)
    assert "detection_summary" in context
    assert "coverage_score" in context
    assert "covered_techniques" in context
    assert "uncovered_techniques" in context
    assert "coverage_gaps" in context
    assert context["coverage_score"] > 0.0


# --- 7. RBAC & Scope Validation Tests ---


@pytest.mark.asyncio
async def test_rbac_detection_scope_validation(client, mock_db) -> None:
    """Verify standard operators/readers are restricted from viewing or mutating detections outside their allowed scopes."""
    scope_own = Scope()
    scope_own.id = SCOPE_ID
    scope_own.owner_id = OPERATOR_ID
    scope_own.deleted_at = None

    scope_other = Scope()
    scope_other.id = SCOPE_ID_2
    scope_other.owner_id = uuid.uuid4()
    scope_other.deleted_at = None

    setup_basic_mock_db(mock_db, scope_own, scope_other)

    # Seed a detection rule in scope_other
    record = DetectionService.create_or_sync_detection("Other Rule", "Desc", "LOW", ["T1059"], SCOPE_ID_2)

    headers = get_auth_header(OPERATOR_ID, "operator")

    # Attempt retrieve -> 403 Forbidden
    res_get = await client.get(f"/api/v1/detections/{record.detection_id}", headers=headers)
    assert res_get.status_code == 403

    # Attempt create in unauthorized scope -> 403 Forbidden
    payload = {
        "name": "Bad API Rule",
        "description": "API Description",
        "severity": "HIGH",
        "attack_techniques": ["T1059"],
        "scope_id": str(SCOPE_ID_2),
    }
    res_post = await client.post("/api/v1/detections", json=payload, headers=headers)
    assert res_post.status_code == 403

    # Attempt mutate status in unauthorized scope -> 403 Forbidden
    res_disable = await client.post(f"/api/v1/detections/{record.detection_id}/disable", headers=headers)
    assert res_disable.status_code == 403
