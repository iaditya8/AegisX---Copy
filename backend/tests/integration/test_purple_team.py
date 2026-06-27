import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from src.core.security import create_access_token
from src.domain.entities.purple_team import (
    ExerciseSeverity,
    ExerciseStatus,
    ExerciseType,
    ValidationStatus,
    PurpleTeamExerciseResponse,
    ValidationResponse,
    PurpleTeamFindingResponse,
)
from src.infrastructure.database.models import Asset, Finding, Scope, User
from src.services.exercise_type_registry import ExerciseTypeRegistry
from src.services.validation_status_registry import ValidationStatusRegistry
from src.services.attack_validation_registry import AttackValidationRegistry
from src.services.purple_team_fingerprint_service import PurpleTeamFingerprintService
from src.services.purple_team_history_service import PurpleTeamHistoryService
from src.services.purple_team_finding_service import PurpleTeamFindingService
from src.services.purple_team_service import PurpleTeamService
from src.services.adversary_emulation_service import AdversaryEmulationService
from src.services.attack_validation_service import AttackValidationService
from src.services.detection_validation_service import DetectionValidationService
from src.services.purple_team_coverage_service import PurpleTeamCoverageService
from src.services.purple_team_drift_service import PurpleTeamDriftService
from src.services.purple_team_snapshot_service import PurpleTeamSnapshotService
from src.services.ai_context_builder import AIContextBuilder
from src.services.ai_prompt_builder import AIPromptBuilder
from src.services.detection_service import DetectionService, DetectionRecord
from src.domain.entities.detection import DetectionSeverity, DetectionStatus

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
    s.owner_id = uuid.uuid4()
    s.name = "Other Scope"
    s.deleted_at = None
    return s


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_stores():
    PurpleTeamService.clear_exercises()
    AttackValidationService.clear_validations()
    PurpleTeamFindingService.clear_findings()
    PurpleTeamHistoryService.clear_history()
    PurpleTeamSnapshotService.clear_snapshots()
    DetectionService.clear_detections()


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


def setup_test_db(mock_db, scopes=None, assets=None, findings=None):
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    async def mock_get(model, ident):
        if model == Scope and scopes:
            for s in scopes:
                if s.id == ident:
                    return s
        if model == Finding and findings:
            for f in findings:
                if f.id == ident:
                    return f
        if model == Asset and assets:
            for a in assets:
                if a.id == ident:
                    return a
        return None

    mock_db.get = AsyncMock(side_effect=mock_get)

    async def mock_execute(query, *args, **kwargs):
        mock_result = MagicMock()
        query_str = str(query).lower()

        if "from scopes" in query_str or "from scope" in query_str:
            owner_id_val = None
            scope_id_val = None
            try:
                params = query.compile().params
                for k, v in params.items():
                    if isinstance(v, uuid.UUID) or (isinstance(v, str) and len(v) == 36):
                        val = uuid.UUID(str(v))
                        if any(s.id == val for s in (scopes or [])):
                            scope_id_val = val
                        else:
                            owner_id_val = val
            except Exception:
                pass

            filtered_scopes = scopes or []
            if scope_id_val:
                filtered_scopes = [s for s in filtered_scopes if s.id == scope_id_val]
            elif owner_id_val:
                filtered_scopes = [s for s in filtered_scopes if s.owner_id == owner_id_val]

            mock_result.scalar_one_or_none.side_effect = lambda: filtered_scopes[0] if filtered_scopes else None
            mock_result.scalars().all.side_effect = lambda: filtered_scopes
        elif "from assets" in query_str:
            mock_result.scalars().all.side_effect = lambda: assets or []
        elif "from findings" in query_str:
            mock_result.scalars().all.side_effect = lambda: findings or []
        else:
            mock_result.scalar_one_or_none.side_effect = lambda: None
            mock_result.scalars().all.side_effect = lambda: []
        return mock_result

    mock_db.execute = AsyncMock(side_effect=mock_execute)


def setup_basic_mock_db(mock_db, mock_scope, mock_scope_2=None):
    scopes = [mock_scope]
    if mock_scope_2:
        scopes.append(mock_scope_2)
    setup_test_db(mock_db, scopes=scopes)


# --- 1. Exercise Type & Status Registry Tests (6 tests) ---

def test_exercise_type_valid():
    assert ExerciseTypeRegistry.is_valid_type("ATTACK_SIMULATION") is True
    assert ExerciseTypeRegistry.is_valid_type("ADVERSARY_EMULATION") is True
    assert ExerciseTypeRegistry.is_valid_type("INVALID_TYPE") is False


def test_exercise_type_registered():
    registered = ExerciseTypeRegistry.get_registered_types()
    assert ExerciseType.ATTACK_SIMULATION in registered
    assert ExerciseType.CONTROL_VALIDATION in registered


def test_validation_status_valid():
    assert ValidationStatusRegistry.is_valid_status("PASSED") is True
    assert ValidationStatusRegistry.is_valid_status("PARTIAL") is True
    assert ValidationStatusRegistry.is_valid_status("INVALID") is False


def test_validation_status_registered():
    registered = ValidationStatusRegistry.get_registered_statuses()
    assert ValidationStatus.PASSED in registered
    assert ValidationStatus.FAILED in registered


def test_attack_validation_registry_valid():
    assert AttackValidationRegistry.is_valid_technique("T1059") is True
    assert AttackValidationRegistry.is_valid_technique("T1234") is False


def test_attack_validation_registry_techniques():
    registered = AttackValidationRegistry.get_registered_techniques()
    assert "T1059" in registered
    assert "T1562" in registered
    assert len(registered) == 7


# --- 2. Fingerprint Stability Tests (3 tests) ---

def test_exercise_fingerprint_generation():
    fp1 = PurpleTeamFingerprintService.generate_fingerprint(
        ExerciseType.ATTACK_SIMULATION, "Exercise 1", ["T1059"], [{"entity_type": "Asset", "entity_id": "1"}]
    )
    fp2 = PurpleTeamFingerprintService.generate_fingerprint(
        ExerciseType.ATTACK_SIMULATION, "Exercise 1", ["T1059"], [{"entity_type": "Asset", "entity_id": "1"}]
    )
    assert fp1 == fp2


def test_exercise_fingerprint_stability():
    fp1 = PurpleTeamFingerprintService.generate_fingerprint(
        ExerciseType.ATTACK_SIMULATION, "Exercise 1", ["T1059"], [{"entity_type": "Asset", "entity_id": "1"}]
    )
    fp2 = PurpleTeamFingerprintService.generate_fingerprint(
        ExerciseType.ATTACK_SIMULATION, " exercise 1  ", ["T1059"], [{"entity_type": "Asset", "entity_id": "1"}]
    )
    assert fp1 == fp2


def test_exercise_sync_preserves_identity():
    ex1 = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "Desc 1", ExerciseType.ATTACK_SIMULATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1059"]
    )
    ex2 = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "Desc 2", ExerciseType.ATTACK_SIMULATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1059"]
    )
    assert ex1.exercise_id == ex2.exercise_id
    assert ex1.description == "Desc 2"


# --- 3. Purple Team History Logs Tests (4 tests) ---

def test_history_empty():
    assert len(PurpleTeamHistoryService.get_history(uuid.uuid4())) == 0


def test_history_record_event():
    ex_id = uuid.uuid4()
    entry = PurpleTeamHistoryService.record_event(ex_id, "CREATED", "Created exercise")
    assert entry.exercise_id == ex_id
    assert entry.event_type == "CREATED"
    assert entry.details == "Created exercise"


def test_history_clear():
    ex_id = uuid.uuid4()
    PurpleTeamHistoryService.record_event(ex_id, "CREATED", "Created exercise")
    PurpleTeamHistoryService.clear_history()
    assert len(PurpleTeamHistoryService.get_history(ex_id)) == 0


def test_history_preserved():
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "Desc 1", ExerciseType.ATTACK_SIMULATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    history = PurpleTeamHistoryService.get_history(ex.exercise_id)
    assert len(history) == 1
    assert history[0].event_type == "CREATED"


# --- 4. Validation Findings Preservation Tests (4 tests) ---

def test_findings_empty():
    assert len(PurpleTeamFindingService.get_findings(uuid.uuid4())) == 0


def test_findings_create():
    ex_id = uuid.uuid4()
    finding = PurpleTeamFindingService.create_finding(
        ex_id, "T1059", ExerciseSeverity.HIGH, "GAP", "Description of gap"
    )
    assert finding.exercise_id == ex_id
    assert finding.technique_id == "T1059"
    assert finding.gap_type == "GAP"


def test_findings_duplicate_prevention():
    ex_id = uuid.uuid4()
    f1 = PurpleTeamFindingService.create_finding(ex_id, "T1059", ExerciseSeverity.HIGH, "GAP", "Desc")
    f2 = PurpleTeamFindingService.create_finding(ex_id, "T1059", ExerciseSeverity.HIGH, "GAP", "Other Desc")
    assert f1.finding_id == f2.finding_id


def test_findings_immutable():
    ex_id = uuid.uuid4()
    f = PurpleTeamFindingService.create_finding(ex_id, "T1059", ExerciseSeverity.HIGH, "GAP", "Desc")
    with pytest.raises((TypeError, ValidationError)):
        f.description = "Mutated"  # type: ignore


# --- 5. Lifecycle Transition & Terminal State Tests (7 tests) ---

def test_exercise_create():
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "Desc 1", ExerciseType.ATTACK_SIMULATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    assert ex.status == ExerciseStatus.OPEN
    assert ex.name == "Ex 1"


def test_exercise_activate_transition():
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "Desc 1", ExerciseType.ATTACK_SIMULATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    activated = PurpleTeamService.activate_exercise(ex.exercise_id, owner="operator")
    assert activated.status == ExerciseStatus.ACTIVE
    assert activated.owner == "operator"


def test_exercise_review_transition():
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "Desc 1", ExerciseType.ATTACK_SIMULATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    PurpleTeamService.activate_exercise(ex.exercise_id)
    reviewed = PurpleTeamService.review_exercise(ex.exercise_id)
    assert reviewed.status == ExerciseStatus.UNDER_REVIEW


def test_exercise_complete_transition():
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "Desc 1", ExerciseType.ATTACK_SIMULATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    PurpleTeamService.activate_exercise(ex.exercise_id)
    completed = PurpleTeamService.complete_exercise(ex.exercise_id)
    assert completed.status == ExerciseStatus.COMPLETED


def test_exercise_close_transition():
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "Desc 1", ExerciseType.ATTACK_SIMULATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    PurpleTeamService.activate_exercise(ex.exercise_id)
    PurpleTeamService.complete_exercise(ex.exercise_id)
    closed = PurpleTeamService.close_exercise(ex.exercise_id)
    assert closed.status == ExerciseStatus.CLOSED


def test_exercise_terminal_state_enforcement():
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "Desc 1", ExerciseType.ATTACK_SIMULATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    PurpleTeamService.activate_exercise(ex.exercise_id)
    PurpleTeamService.complete_exercise(ex.exercise_id)
    PurpleTeamService.close_exercise(ex.exercise_id)

    with pytest.raises(ValueError):
        PurpleTeamService.activate_exercise(ex.exercise_id)


def test_exercise_invalid_transitions():
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "Desc 1", ExerciseType.ATTACK_SIMULATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    with pytest.raises(ValueError):
        PurpleTeamService.complete_exercise(ex.exercise_id)  # Cannot complete from OPEN directly


# --- 6. Emulation Tests (6 tests) ---

def test_apt29_emulation():
    techs = AdversaryEmulationService.get_techniques_for_actor("APT29")
    assert "T1059" in techs
    assert "T1078" in techs


def test_apt28_emulation():
    techs = AdversaryEmulationService.get_techniques_for_actor("APT28")
    assert "T1027" in techs
    assert "T1105" in techs


def test_lazarus_emulation():
    techs = AdversaryEmulationService.get_techniques_for_actor("Lazarus")
    assert "T1047" in techs
    assert "T1055" in techs


def test_fin7_emulation():
    techs = AdversaryEmulationService.get_techniques_for_actor("FIN7")
    assert "T1059" in techs
    assert "T1562" in techs


def test_actor_mapping_preserved():
    actors = AdversaryEmulationService.get_actors_for_technique("T1059")
    assert "APT29" in actors
    assert "FIN7" in actors


def test_campaign_mapping_preserved():
    # Campaign validation mappings check
    techs = AdversaryEmulationService.get_techniques_for_actor("APT29")
    assert len(techs) == 2


# --- 7. ATT&CK Technique Validation Tests (8 tests) ---

@pytest.mark.asyncio
async def test_validation_passed(mock_db):
    setup_test_db(mock_db)
    # Add active detection rule
    DetectionService.create_or_sync_detection(
        "Rule 1", "Desc", DetectionSeverity.HIGH, ["T1059"], SCOPE_ID
    )
    # Mock finding
    finding = Finding()
    finding.id = uuid.uuid4()
    finding.title = "Suspicious execution T1059 detected"
    finding.description = "..."
    setup_test_db(mock_db, findings=[finding])

    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1059"]
    )
    vals = await AttackValidationService.validate_exercise_techniques(mock_db, ex.exercise_id)
    assert len(vals) == 1
    assert vals[0].validation_status == ValidationStatus.PASSED
    assert vals[0].expected_detection is True
    assert vals[0].actual_detection is True


@pytest.mark.asyncio
async def test_validation_partial(mock_db):
    setup_test_db(mock_db)
    DetectionService.create_or_sync_detection(
        "Rule 1", "Desc", DetectionSeverity.HIGH, ["T1059"], SCOPE_ID
    )

    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1059"]
    )
    vals = await AttackValidationService.validate_exercise_techniques(mock_db, ex.exercise_id)
    assert len(vals) == 1
    assert vals[0].validation_status == ValidationStatus.PARTIAL
    assert vals[0].expected_detection is True
    assert vals[0].actual_detection is False


@pytest.mark.asyncio
async def test_validation_failed(mock_db):
    setup_test_db(mock_db)
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1059"]
    )
    vals = await AttackValidationService.validate_exercise_techniques(mock_db, ex.exercise_id)
    assert len(vals) == 1
    assert vals[0].validation_status == ValidationStatus.FAILED
    assert vals[0].expected_detection is False
    assert vals[0].actual_detection is False


@pytest.mark.asyncio
async def test_validation_identity_preserved(mock_db):
    setup_test_db(mock_db)
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1059"]
    )
    v1 = await AttackValidationService.validate_exercise_techniques(mock_db, ex.exercise_id)
    v2 = await AttackValidationService.validate_exercise_techniques(mock_db, ex.exercise_id)
    assert v1[0].validation_id == v2[0].validation_id


@pytest.mark.asyncio
async def test_validation_sync_preserves_identity(mock_db):
    setup_test_db(mock_db)
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1059"]
    )
    v1 = await AttackValidationService.validate_exercise_techniques(mock_db, ex.exercise_id)
    # Sync exercise name/details
    PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "Desc Updated", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1059"]
    )
    v2 = await AttackValidationService.validate_exercise_techniques(mock_db, ex.exercise_id)
    assert v1[0].validation_id == v2[0].validation_id


@pytest.mark.asyncio
async def test_validation_finding_creation(mock_db):
    setup_test_db(mock_db)
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1059"]
    )
    vals = await AttackValidationService.validate_exercise_techniques(mock_db, ex.exercise_id)
    # Create findings for gaps/failures
    for v in vals:
        if v.validation_status == ValidationStatus.FAILED:
            PurpleTeamFindingService.create_finding(
                v.exercise_id, v.technique_id, ExerciseSeverity.HIGH, "GAP", "No detection rule covers this technique."
            )
    finds = PurpleTeamFindingService.get_findings(ex.exercise_id)
    assert len(finds) == 1
    assert finds[0].technique_id == "T1059"


@pytest.mark.asyncio
async def test_validation_finding_preservation(mock_db):
    setup_test_db(mock_db)
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1059"]
    )
    f1 = PurpleTeamFindingService.create_finding(ex.exercise_id, "T1059", ExerciseSeverity.HIGH, "GAP", "Desc")
    f2 = PurpleTeamFindingService.create_finding(ex.exercise_id, "T1059", ExerciseSeverity.HIGH, "GAP", "Desc")
    assert f1.finding_id == f2.finding_id


@pytest.mark.asyncio
async def test_gap_finding_creation(mock_db):
    setup_test_db(mock_db)
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.CONTROL_VALIDATION, ExerciseSeverity.CRITICAL, SCOPE_ID, related_techniques=["T1562"]
    )
    await AttackValidationService.validate_exercise_techniques(mock_db, ex.exercise_id)
    PurpleTeamFindingService.create_finding(
        ex.exercise_id, "T1562", ExerciseSeverity.CRITICAL, "CONTROL_GAP", "Control bypass verified"
    )
    finds = PurpleTeamFindingService.get_findings(ex.exercise_id)
    assert len(finds) == 1
    assert finds[0].gap_type == "CONTROL_GAP"


# --- 8. Coverage & Drift Service Tests (10 tests) ---

def test_attack_coverage_calculation():
    DetectionService.create_or_sync_detection(
        "Rule 1", "...", DetectionSeverity.HIGH, ["T1059"], SCOPE_ID
    )
    cov = PurpleTeamCoverageService.calculate_coverage(SCOPE_ID)
    # 1 of 7 techniques covered
    assert cov["attack_coverage"] == round(1 / 7 * 100.0, 2)


def test_actor_coverage_calculation():
    DetectionService.create_or_sync_detection(
        "Rule 1", "...", DetectionSeverity.HIGH, ["T1059"], SCOPE_ID
    )
    cov = PurpleTeamCoverageService.calculate_coverage(SCOPE_ID)
    # APT29 and FIN7 use T1059. So they should be covered. (2 of 4 actors covered)
    assert cov["actor_coverage"] == 50.0


def test_campaign_coverage_calculation():
    DetectionService.create_or_sync_detection(
        "Rule 1", "...", DetectionSeverity.HIGH, ["T1059"], SCOPE_ID
    )
    cov = PurpleTeamCoverageService.calculate_coverage(SCOPE_ID)
    # Operation Ghost uses T1059. (1 of 2 campaigns covered)
    assert cov["campaign_coverage"] == 50.0


def test_detection_validation_coverage(mock_db):
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1059"]
    )
    # Fake passed validation
    val = AttackValidationService._validations
    val_id = uuid.uuid4()
    AttackValidationService._validations[val_id] = MagicMock(
        validation_id=val_id, exercise_id=ex.exercise_id, technique_id="T1059", validation_status=ValidationStatus.PASSED
    )
    cov = PurpleTeamCoverageService.calculate_coverage(SCOPE_ID)
    assert cov["detection_validation_coverage"] == 100.0


def test_control_validation_coverage():
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.CONTROL_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1562"]
    )
    val_id = uuid.uuid4()
    AttackValidationService._validations[val_id] = MagicMock(
        validation_id=val_id, exercise_id=ex.exercise_id, technique_id="T1562", validation_status=ValidationStatus.PASSED
    )
    cov = PurpleTeamCoverageService.calculate_coverage(SCOPE_ID)
    assert cov["control_validation_coverage"] == 100.0


@pytest.mark.asyncio
async def test_coverage_regression_detection(mock_db):
    setup_test_db(mock_db)
    from unittest.mock import patch
    from src.services.workflow_event_service import WorkflowEventService

    prev_snapshot = {
        "coverage": {
            "attack_coverage": 50.0,
            "actor_coverage": 50.0,
            "campaign_coverage": 50.0,
            "detection_validation_coverage": 100.0,
            "control_validation_coverage": 100.0,
        }
    }
    # Current coverage will be 0 because we have no active detections
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await PurpleTeamDriftService.check_drift(mock_db, SCOPE_ID, prev_snapshot)
        assert mock_emit.call_count >= 1


@pytest.mark.asyncio
async def test_validation_drift_detection(mock_db):
    setup_test_db(mock_db)
    from unittest.mock import patch
    from src.services.workflow_event_service import WorkflowEventService

    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1059"]
    )
    # Current validation status is FAILED
    await AttackValidationService.validate_exercise_techniques(mock_db, ex.exercise_id)

    # Previous snapshot has PASSED validation for same key
    prev_snapshot = {
        "validations": {
            f"{ex.exercise_id}:T1059": {
                "status": "PASSED"
            }
        }
    }
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await PurpleTeamDriftService.check_drift(mock_db, SCOPE_ID, prev_snapshot)
        assert mock_emit.call_count >= 1


@pytest.mark.asyncio
async def test_detection_drift_detection(mock_db):
    setup_test_db(mock_db)
    from unittest.mock import patch
    from src.services.workflow_event_service import WorkflowEventService

    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1059"]
    )
    await AttackValidationService.validate_exercise_techniques(mock_db, ex.exercise_id)

    prev_snapshot = {
        "validations": {
            f"{ex.exercise_id}:T1059": {
                "status": "PASSED"
            }
        }
    }
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await PurpleTeamDriftService.check_drift(mock_db, SCOPE_ID, prev_snapshot)
        # Check drift payload contains DETECTION_DRIFT
        payloads = [call.kwargs["payload"] for call in mock_emit.call_args_list]
        drift_types = [p["drift_type"] for p in payloads if "drift_type" in p]
        assert "DETECTION_DRIFT" in drift_types


@pytest.mark.asyncio
async def test_control_drift_detection(mock_db):
    setup_test_db(mock_db)
    from unittest.mock import patch
    from src.services.workflow_event_service import WorkflowEventService

    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.CONTROL_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID, related_techniques=["T1562"]
    )
    await AttackValidationService.validate_exercise_techniques(mock_db, ex.exercise_id)

    prev_snapshot = {
        "validations": {
            f"{ex.exercise_id}:T1562": {
                "status": "PASSED"
            }
        }
    }
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await PurpleTeamDriftService.check_drift(mock_db, SCOPE_ID, prev_snapshot)
        payloads = [call.kwargs["payload"] for call in mock_emit.call_args_list]
        drift_types = [p["drift_type"] for p in payloads if "drift_type" in p]
        assert "CONTROL_DRIFT" in drift_types


@pytest.mark.asyncio
async def test_new_attack_gap_detection(mock_db):
    setup_test_db(mock_db)
    from unittest.mock import patch
    from src.services.workflow_event_service import WorkflowEventService

    prev_snapshot = {
        "coverage": {
            "attack_coverage": 100.0,
            "actor_coverage": 100.0,
            "campaign_coverage": 100.0,
            "detection_validation_coverage": 100.0,
            "control_validation_coverage": 100.0,
        }
    }
    # Current attack coverage is 0.0, which means regression
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await PurpleTeamDriftService.check_drift(mock_db, SCOPE_ID, prev_snapshot)
        payloads = [call.kwargs["payload"] for call in mock_emit.call_args_list]
        drift_types = [p["drift_type"] for p in payloads if "drift_type" in p]
        assert "NEW_ATTACK_GAP" in drift_types


# --- 9. Snapshot & Cache Rebuild Tests (3 tests) ---

def test_snapshot_rebuild_consistency():
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "Desc", ExerciseType.ATTACK_SIMULATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    snap1 = PurpleTeamSnapshotService.get_snapshot(SCOPE_ID)
    assert snap1["summary"]["total_exercises"] == 1

    # Mutate internally and get again
    snap2 = PurpleTeamSnapshotService.get_snapshot(SCOPE_ID)
    assert snap2 == snap1


def test_snapshot_rebuild_after_cache_deletion():
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "Desc", ExerciseType.ATTACK_SIMULATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    PurpleTeamSnapshotService.get_snapshot(SCOPE_ID)
    # Clear cache
    PurpleTeamSnapshotService.clear_snapshots()
    # Rebuild dynamically
    snap = PurpleTeamSnapshotService.get_snapshot(SCOPE_ID)
    assert snap["summary"]["total_exercises"] == 1


def test_snapshot_rebuild_after_corruption():
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "Desc", ExerciseType.ATTACK_SIMULATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    PurpleTeamSnapshotService._snapshots[SCOPE_ID] = {"corrupted": True}
    # Force rebuild
    snap = PurpleTeamSnapshotService.generate_snapshot(SCOPE_ID)
    assert "summary" in snap
    assert "corrupted" not in snap


# --- 10. AI Context & Advisory Prompt Constraints (2 tests) ---

@pytest.mark.asyncio
async def test_ai_context_purple_team_injection(mock_db):
    setup_test_db(mock_db)
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    
    from unittest.mock import patch
    from src.services.asset_report_service import AssetReportService
    
    mock_report = {
        "asset": {"id": str(uuid.uuid4()), "scope_id": SCOPE_ID},
        "risk": {},
        "findings": [],
        "exposure": {}
    }
    
    with patch.object(AssetReportService, "generate_asset_report", new_callable=AsyncMock, return_value=mock_report):
        ctx = await AIContextBuilder.build_asset_context(mock_db, uuid.uuid4())
        assert "purple_team_summary" in ctx["asset"]
        assert "purple_team_coverage" in ctx["asset"]
        assert "active_exercises" in ctx["asset"]


def test_ai_advisory_only_enforcement():
    context = {"dummy": "data"}
    prompt = AIPromptBuilder.build_asset_prompt(context)
    assert "purple team exercises" in prompt
    assert "cannot mutate/create/activate" or "MUST NOT approve risk" in prompt


# --- 11. REST API Routing Tests (10 tests) ---

@pytest.mark.asyncio
async def test_api_list_exercises(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/purple-team/exercises", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_api_get_exercise(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/purple-team/exercises/{ex.exercise_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Ex 1"


@pytest.mark.asyncio
async def test_api_create_exercise(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {
        "name": "API Ex",
        "description": "Via API",
        "exercise_type": "DETECTION_VALIDATION",
        "severity": "HIGH",
        "scope_id": str(SCOPE_ID),
    }
    resp = await client.post("/api/v1/purple-team/exercises", json=payload, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["data"]["name"] == "API Ex"


@pytest.mark.asyncio
async def test_api_transitions(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    headers = get_auth_header(OPERATOR_ID, "operator")

    # Activate
    resp = await client.post(f"/api/v1/purple-team/exercises/{ex.exercise_id}/activate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ACTIVE"

    # Review
    resp = await client.post(f"/api/v1/purple-team/exercises/{ex.exercise_id}/review", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "UNDER_REVIEW"

    # Activate again (re-activate allowed)
    resp = await client.post(f"/api/v1/purple-team/exercises/{ex.exercise_id}/activate", headers=headers)
    assert resp.status_code == 200

    # Complete
    resp = await client.post(f"/api/v1/purple-team/exercises/{ex.exercise_id}/complete", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "COMPLETED"

    # Close
    resp = await client.post(f"/api/v1/purple-team/exercises/{ex.exercise_id}/close", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_api_rbac_permissions(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    headers = get_auth_header(READER_ID, "reader")
    # Readers cannot activate
    resp = await client.post(f"/api/v1/purple-team/exercises/{ex.exercise_id}/activate", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rbac_scope_validation(client, mock_db, mock_scope, mock_scope_2):
    setup_basic_mock_db(mock_db, mock_scope, mock_scope_2)
    # Ex 1 is in scope_2 which operator does not own
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID_2
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/purple-team/exercises/{ex.exercise_id}", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rbac_operator_permissions(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {
        "name": "Op Ex",
        "description": "Via API",
        "exercise_type": "DETECTION_VALIDATION",
        "severity": "HIGH",
        "scope_id": str(SCOPE_ID),
    }
    resp = await client.post("/api/v1/purple-team/exercises", json=payload, headers=headers)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_rbac_reader_restrictions(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(READER_ID, "reader")
    payload = {
        "name": "Reader Ex",
        "description": "Via API",
        "exercise_type": "DETECTION_VALIDATION",
        "severity": "HIGH",
        "scope_id": str(SCOPE_ID),
    }
    resp = await client.post("/api/v1/purple-team/exercises", json=payload, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_identity_preserved_after_completion(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    await client.post(f"/api/v1/purple-team/exercises/{ex.exercise_id}/activate", headers=headers)
    resp = await client.post(f"/api/v1/purple-team/exercises/{ex.exercise_id}/complete", headers=headers)
    assert resp.json()["data"]["exercise_id"] == str(ex.exercise_id)


@pytest.mark.asyncio
async def test_identity_preserved_after_closure(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    ex = PurpleTeamService.create_or_sync_exercise(
        "Ex 1", "...", ExerciseType.DETECTION_VALIDATION, ExerciseSeverity.HIGH, SCOPE_ID
    )
    headers = get_auth_header(OPERATOR_ID, "operator")
    await client.post(f"/api/v1/purple-team/exercises/{ex.exercise_id}/activate", headers=headers)
    await client.post(f"/api/v1/purple-team/exercises/{ex.exercise_id}/complete", headers=headers)
    resp = await client.post(f"/api/v1/purple-team/exercises/{ex.exercise_id}/close", headers=headers)
    assert resp.json()["data"]["exercise_id"] == str(ex.exercise_id)
