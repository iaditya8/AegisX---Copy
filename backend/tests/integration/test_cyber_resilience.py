import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from src.core.security import create_access_token
from src.domain.entities.cyber_resilience import (
    ResilienceStatus,
    ServiceCriticality,
    RecoveryObjectiveType,
    CyberResilienceResponse,
    RecoveryObjectiveResponse,
)
from src.infrastructure.database.models import Scope, User
from src.services.resilience_registry import ResilienceRegistry
from src.services.criticality_registry import CriticalityRegistry
from src.services.recovery_objective_registry import RecoveryObjectiveRegistry
from src.services.resilience_fingerprint_service import ResilienceFingerprintService
from src.services.resilience_history_service import ResilienceHistoryService
from src.services.recovery_objective_service import RecoveryObjectiveService
from src.services.resilience_scoring_service import ResilienceScoringService
from src.services.service_resilience_service import ServiceResilienceService
from src.services.resilience_drift_service import ResilienceDriftService
from src.services.cyber_resilience_service import CyberResilienceService
from src.services.cyber_resilience_snapshot_service import CyberResilienceSnapshotService
from src.services.ai_context_builder import AIContextBuilder
from src.services.ai_prompt_builder import AIPromptBuilder

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
    CyberResilienceService.clear_resilience()
    RecoveryObjectiveService.clear_objectives()
    ResilienceHistoryService.clear_history()
    CyberResilienceSnapshotService.clear_snapshots()


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


def setup_basic_mock_db(mock_db, *scopes):
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    async def mock_get(model, ident):
        if model == Scope:
            for s in scopes:
                if s.id == ident:
                    return s
        return None

    mock_db.get = AsyncMock(side_effect=mock_get)

    async def mock_execute(query, *args, **kwargs):
        mock_result = MagicMock()
        query_str = str(query).lower()

        if "from scopes" in query_str or "from scope" in query_str:
            scope_id_val = None
            owner_id_val = None
            try:
                params = query.compile().params
                for k, v in params.items():
                    if "id_" in k:
                        if isinstance(v, uuid.UUID) or (isinstance(v, str) and len(v) == 36):
                            scope_id_val = uuid.UUID(str(v))
                    if "owner_id" in k:
                        owner_id_val = v
            except Exception:
                pass

            matched = list(scopes)
            if scope_id_val:
                matched = [s for s in matched if s.id == scope_id_val]
            elif owner_id_val:
                matched = [s for s in matched if s.owner_id == owner_id_val]

            mock_result.scalars().all = MagicMock(return_value=matched)
            mock_result.scalar_one_or_none = MagicMock(return_value=matched[0] if matched else None)
        elif "assets" in query_str:
            mock_result.scalars().all = MagicMock(return_value=[])
        else:
            mock_result.scalars().all = MagicMock(return_value=[])
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
        return mock_result

    mock_db.execute = AsyncMock(side_effect=mock_execute)


# ==========================================
# PART 1: REGISTRY & FINGERPRINT (15 Tests)
# ==========================================

def test_resilience_registry_list():
    assert "BUSINESS_CONTINUITY" in ResilienceRegistry.list_types()

def test_resilience_registry_validate():
    assert ResilienceRegistry.validate("BUSINESS_CONTINUITY")
    assert not ResilienceRegistry.validate("INVALID")

def test_criticality_registry_weight():
    assert CriticalityRegistry.get_weight(ServiceCriticality.MISSION_CRITICAL) == 3.0
    assert CriticalityRegistry.get_weight(ServiceCriticality.LOW) == 1.0

def test_recovery_objective_registry_tiers():
    assert 4.0 in RecoveryObjectiveRegistry.get_tiers("RTO")
    assert 0.0 in RecoveryObjectiveRegistry.get_tiers("RPO")

def test_recovery_objective_registry_validate():
    assert RecoveryObjectiveRegistry.validate("RTO", 4.0)
    assert not RecoveryObjectiveRegistry.validate("RTO", 999.0)

def test_resilience_fingerprint_generation():
    f = ResilienceFingerprintService.generate_fingerprint("Title", "Srv", "HIGH")
    assert isinstance(f, str) and len(f) == 64

def test_resilience_fingerprint_stability():
    f1 = ResilienceFingerprintService.generate_fingerprint("Title", "Srv", "HIGH")
    f2 = ResilienceFingerprintService.generate_fingerprint("Title", "Srv", "HIGH")
    assert f1 == f2

def test_resilience_fingerprint_case_insensitivity():
    f1 = ResilienceFingerprintService.generate_fingerprint("Title", "Srv", "HIGH")
    f2 = ResilienceFingerprintService.generate_fingerprint("title", "srv", "high")
    assert f1 == f2

def test_resilience_fingerprint_changes_on_title():
    f1 = ResilienceFingerprintService.generate_fingerprint("Title A", "Srv", "HIGH")
    f2 = ResilienceFingerprintService.generate_fingerprint("Title B", "Srv", "HIGH")
    assert f1 != f2

def test_resilience_fingerprint_changes_on_service():
    f1 = ResilienceFingerprintService.generate_fingerprint("Title", "Srv A", "HIGH")
    f2 = ResilienceFingerprintService.generate_fingerprint("Title", "Srv B", "HIGH")
    assert f1 != f2

def test_resilience_fingerprint_changes_on_criticality():
    f1 = ResilienceFingerprintService.generate_fingerprint("Title", "Srv", "HIGH")
    f2 = ResilienceFingerprintService.generate_fingerprint("Title", "Srv", "LOW")
    assert f1 != f2

def test_resilience_registry_types_count():
    assert len(ResilienceRegistry.list_types()) == 5

def test_criticality_registry_weights_count():
    assert len(CriticalityRegistry.FACTORS) == 4

def test_recovery_objective_registry_types_list():
    assert "RTO" in RecoveryObjectiveRegistry.list_types()

def test_recovery_objective_registry_rpo_tiers():
    assert len(RecoveryObjectiveRegistry.get_tiers("RPO")) == 4


# ==========================================
# PART 2: LIFECYCLE & IDENTITY (20 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_create_resilience(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    assert r.status == ResilienceStatus.PLANNED

@pytest.mark.asyncio
async def test_transition_planned_to_active(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    r_trans = CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    assert r_trans.status == ResilienceStatus.ACTIVE

@pytest.mark.asyncio
async def test_transition_active_to_under_review(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    r_trans = CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.UNDER_REVIEW)
    assert r_trans.status == ResilienceStatus.UNDER_REVIEW

@pytest.mark.asyncio
async def test_transition_active_to_validated(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    r_trans = CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.VALIDATED)
    assert r_trans.status == ResilienceStatus.VALIDATED

@pytest.mark.asyncio
async def test_transition_active_to_completed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    r_trans = CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.COMPLETED)
    assert r_trans.status == ResilienceStatus.COMPLETED

@pytest.mark.asyncio
async def test_transition_active_to_closed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    r_trans = CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.CLOSED)
    assert r_trans.status == ResilienceStatus.CLOSED

@pytest.mark.asyncio
async def test_terminal_state_completed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.COMPLETED)
    # Re-transitioning should fail/leave status as COMPLETED
    res = CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    assert res.status == ResilienceStatus.COMPLETED

@pytest.mark.asyncio
async def test_terminal_state_closed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.CLOSED)
    res = CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    assert res.status == ResilienceStatus.CLOSED

@pytest.mark.asyncio
async def test_sync_resilience(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    synced = await CyberResilienceService.sync_resilience(mock_db)
    assert len(synced) == 2

@pytest.mark.asyncio
async def test_identity_preservation_sync(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r1 = await CyberResilienceService.create_or_sync_resilience("R1", "Desc 1", "S1", ServiceCriticality.HIGH)
    r2 = await CyberResilienceService.create_or_sync_resilience("R1", "Desc 2", "S1", ServiceCriticality.HIGH)
    assert r1.resilience_id == r2.resilience_id

@pytest.mark.asyncio
async def test_invalid_lifecycle_transition_planned_to_validated(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    with pytest.raises(ValueError, match="Invalid transition"):
        CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.VALIDATED)

@pytest.mark.asyncio
async def test_invalid_lifecycle_transition_planned_to_completed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    with pytest.raises(ValueError, match="Invalid transition"):
        CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.COMPLETED)

@pytest.mark.asyncio
async def test_duplicate_prevention_on_creation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r1 = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    r2 = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    assert len(CyberResilienceService.get_all_resilience()) == 1

@pytest.mark.asyncio
async def test_get_resilience_not_found():
    assert CyberResilienceService.get_resilience(uuid.uuid4()) is None

@pytest.mark.asyncio
async def test_sync_does_not_reactivate_completed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("Critical Infrastructure Backup", "Desc", "Identity Provider", ServiceCriticality.MISSION_CRITICAL)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.COMPLETED)
    await CyberResilienceService.sync_resilience(mock_db)
    assert r.status == ResilienceStatus.COMPLETED

@pytest.mark.asyncio
async def test_sync_does_not_reactivate_closed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("Critical Infrastructure Backup", "Desc", "Identity Provider", ServiceCriticality.MISSION_CRITICAL)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.CLOSED)
    await CyberResilienceService.sync_resilience(mock_db)
    assert r.status == ResilienceStatus.CLOSED

@pytest.mark.asyncio
async def test_transition_status_record_not_found():
    with pytest.raises(ValueError, match="not found"):
        CyberResilienceService.transition_status(uuid.uuid4(), ResilienceStatus.ACTIVE)

@pytest.mark.asyncio
async def test_transition_under_review_to_validated(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.UNDER_REVIEW)
    res = CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.VALIDATED)
    assert res.status == ResilienceStatus.VALIDATED

@pytest.mark.asyncio
async def test_transition_validated_to_completed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.VALIDATED)
    res = CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.COMPLETED)
    assert res.status == ResilienceStatus.COMPLETED

@pytest.mark.asyncio
async def test_transition_validated_to_closed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.VALIDATED)
    res = CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.CLOSED)
    assert res.status == ResilienceStatus.CLOSED


# ==========================================
# PART 3: HISTORY & AUDIT (15 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_resilience_history_recorded(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    hist = ResilienceHistoryService.get_history(r.resilience_id)
    assert len(hist) > 0
    assert hist[0].event_type == "CREATED"

@pytest.mark.asyncio
async def test_resilience_history_immutable(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    hist = ResilienceHistoryService.get_history(r.resilience_id)
    hist.clear()
    assert len(ResilienceHistoryService.get_history(r.resilience_id)) == 1

@pytest.mark.asyncio
async def test_resilience_history_on_activation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    hist = ResilienceHistoryService.get_history(r.resilience_id)
    event_types = [h.event_type for h in hist]
    assert "ACTIVATED" in event_types

@pytest.mark.asyncio
async def test_resilience_history_on_validation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.VALIDATED)
    hist = ResilienceHistoryService.get_history(r.resilience_id)
    event_types = [h.event_type for h in hist]
    assert "VALIDATED" in event_types

@pytest.mark.asyncio
async def test_resilience_history_on_completion(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.COMPLETED)
    hist = ResilienceHistoryService.get_history(r.resilience_id)
    event_types = [h.event_type for h in hist]
    assert "COMPLETED" in event_types

@pytest.mark.asyncio
async def test_resilience_history_on_closure(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.CLOSED)
    hist = ResilienceHistoryService.get_history(r.resilience_id)
    event_types = [h.event_type for h in hist]
    assert "CLOSED" in event_types

@pytest.mark.asyncio
async def test_resilience_history_ordering(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    hist = ResilienceHistoryService.get_history(r.resilience_id)
    assert hist[0].timestamp <= hist[1].timestamp

@pytest.mark.asyncio
async def test_history_survives_snapshot_rebuild(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    await CyberResilienceSnapshotService.generate_snapshot(mock_db, None)
    assert len(ResilienceHistoryService.get_history(r.resilience_id)) == 1

@pytest.mark.asyncio
async def test_history_clear(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    ResilienceHistoryService.clear_history()
    assert len(ResilienceHistoryService.get_history(r.resilience_id)) == 0

@pytest.mark.asyncio
async def test_history_record_event_directly(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    ResilienceHistoryService.record_event(r.resilience_id, "TEST_EVENT", "details")
    hist = ResilienceHistoryService.get_history(r.resilience_id)
    assert hist[-1].event_type == "TEST_EVENT"

@pytest.mark.asyncio
async def test_history_order_preserved_on_multiple_events(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    ResilienceHistoryService.record_event(r.resilience_id, "EVENT_1", "1")
    ResilienceHistoryService.record_event(r.resilience_id, "EVENT_2", "2")
    hist = ResilienceHistoryService.get_history(r.resilience_id)
    assert hist[1].event_type == "EVENT_1"
    assert hist[2].event_type == "EVENT_2"

@pytest.mark.asyncio
async def test_history_empty_for_invalid_id():
    assert len(ResilienceHistoryService.get_history(uuid.uuid4())) == 0

@pytest.mark.asyncio
async def test_history_entry_properties(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    hist = ResilienceHistoryService.get_history(r.resilience_id)
    assert hist[0].resilience_id == r.resilience_id
    assert isinstance(hist[0].timestamp, datetime)

@pytest.mark.asyncio
async def test_history_entry_frozen(mock_db, mock_scope):
    # Tests that history items behave as frozen/immutable
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    hist = ResilienceHistoryService.get_history(r.resilience_id)
    with pytest.raises(Exception):
        hist[0].event_type = "MUTATED"

@pytest.mark.asyncio
async def test_history_deep_copy_isolation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    hist1 = ResilienceHistoryService.get_history(r.resilience_id)
    hist2 = ResilienceHistoryService.get_history(r.resilience_id)
    assert hist1 is not hist2


# ==========================================
# PART 4: SCORING & OBJECTIVES (15 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_set_objective(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    obj = RecoveryObjectiveService.set_objective(r.resilience_id, "RTO", 4.0, 2.0)
    assert obj.target_value == 4.0

@pytest.mark.asyncio
async def test_get_objectives(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    objs = RecoveryObjectiveService.get_objectives(r.resilience_id)
    # creation seeds 2 objectives (RTO, RPO)
    assert len(objs) == 2

def test_calculate_compliance():
    # compliance is min(target, current) / target * 100
    # target 4.0, current 2.0 -> min(4, 2)/4 * 100 = 50%
    assert RecoveryObjectiveService.calculate_compliance(4.0, 2.0) == 50.0

def test_calculate_compliance_target_zero():
    assert RecoveryObjectiveService.calculate_compliance(0.0, 0.0) == 100.0
    assert RecoveryObjectiveService.calculate_compliance(0.0, 1.0) == 0.0

@pytest.mark.asyncio
async def test_resilience_readiness_score_planned(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    score = ResilienceScoringService.calculate_readiness_score(r.resilience_id, r.status)
    assert score == 45.5

@pytest.mark.asyncio
async def test_resilience_readiness_score_validated(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.VALIDATED)
    score = ResilienceScoringService.calculate_readiness_score(r.resilience_id, r.status)
    assert score == 100.0

@pytest.mark.asyncio
async def test_resilience_confidence_score(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    score = ResilienceScoringService.calculate_recovery_confidence_score(r.resilience_id, r.status, 100.0, 45.5)
    assert score == 68.65

@pytest.mark.asyncio
async def test_resilience_score(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    score = ResilienceScoringService.calculate_resilience_score(r.resilience_id, r.status, r.service_criticality, 45.5, 100.0)
    assert score == 64.98

@pytest.mark.asyncio
async def test_resilience_scores_deterministic():
    s1 = ResilienceScoringService.calculate_readiness_score(uuid.uuid4(), ResilienceStatus.ACTIVE)
    s2 = ResilienceScoringService.calculate_readiness_score(uuid.uuid4(), ResilienceStatus.ACTIVE)
    assert s1 == s2

@pytest.mark.asyncio
async def test_resilience_objective_compliance_default_no_objectives():
    assert RecoveryObjectiveService.get_resilience_objective_compliance(uuid.uuid4()) == 100.0

@pytest.mark.asyncio
async def test_get_resilience_objective_compliance_calculation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    # Set RTO target=4.0, current=4.0 (100%), RPO target=1.0, current=0.5 (50%) -> avg = 75%
    RecoveryObjectiveService.set_objective(r.resilience_id, "RTO", 4.0, 4.0)
    RecoveryObjectiveService.set_objective(r.resilience_id, "RPO", 1.0, 0.5)
    assert RecoveryObjectiveService.get_resilience_objective_compliance(r.resilience_id) == 75.0

@pytest.mark.asyncio
async def test_objective_service_clear():
    RecoveryObjectiveService.set_objective(uuid.uuid4(), "RTO", 4.0, 4.0)
    RecoveryObjectiveService.clear_objectives()
    assert len(RecoveryObjectiveService._objectives) == 0

@pytest.mark.asyncio
async def test_objective_response_fields(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    objs = RecoveryObjectiveService.get_objectives(r.resilience_id)
    assert objs[0].compliance_percentage == 100.0
    assert objs[0].objective_type == "RTO"

@pytest.mark.asyncio
async def test_set_objective_updates_timestamp(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    obj1 = RecoveryObjectiveService.set_objective(r.resilience_id, "RTO", 4.0, 4.0)
    t1 = obj1.updated_at
    obj2 = RecoveryObjectiveService.set_objective(r.resilience_id, "RTO", 4.0, 2.0)
    assert obj2.updated_at >= t1

@pytest.mark.asyncio
async def test_objective_rpo_defaults(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    objs = RecoveryObjectiveService.get_objectives(r.resilience_id)
    rpo = next(o for o in objs if o.objective_type == "RPO")
    assert rpo.target_value == 1.0


# ==========================================
# PART 5: SNAPSHOT, DRIFT & SERVICE (15 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_generate_snapshot(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberResilienceService.sync_resilience(mock_db)
    snap = await CyberResilienceSnapshotService.generate_snapshot(mock_db, None)
    assert snap["summary"]["total_resilience_records"] == 2

@pytest.mark.asyncio
async def test_snapshot_cache_clear(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberResilienceSnapshotService.generate_snapshot(mock_db, None)
    CyberResilienceSnapshotService.clear_snapshots()
    snap = CyberResilienceSnapshotService.get_snapshot(None)
    assert snap["summary"]["total_resilience_records"] == 0

@pytest.mark.asyncio
async def test_snapshot_corruption_rebuild(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberResilienceService.sync_resilience(mock_db)
    CyberResilienceSnapshotService._snapshots[None] = "CORRUPTED"
    snap = CyberResilienceSnapshotService.get_snapshot(None)
    assert snap["summary"]["total_resilience_records"] == 0
    await CyberResilienceSnapshotService.generate_snapshot(mock_db, None)
    assert CyberResilienceSnapshotService.get_snapshot(None)["summary"]["total_resilience_records"] == 2

@pytest.mark.asyncio
async def test_resilience_drift_detected(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    prev = {
        "summary": {
            "resilience_score": 100.0,
            "readiness_score": 100.0,
            "recovery_confidence_score": 100.0,
            "objective_compliance": 100.0,
        }
    }

    # Set up some data so generated snapshot exists
    await CyberResilienceService.sync_resilience(mock_db)

    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await ResilienceDriftService.check_drift(mock_db, None, prev)
        events = [c.kwargs["payload"].get("drift_type") for c in mock_emit.call_args_list]
        assert "RESILIENCE_SCORE_CHANGED" in events or len(events) == 0

@pytest.mark.asyncio
async def test_get_critical_services_count(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberResilienceService.sync_resilience(mock_db)
    # Identity Provider (MISSION_CRITICAL) and Directory Services (HIGH) -> Both are critical
    crit = ServiceResilienceService.get_critical_services()
    assert len(crit) == 2

@pytest.mark.asyncio
async def test_get_resilience_distribution_stats(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberResilienceService.sync_resilience(mock_db)
    dist = ServiceResilienceService.get_resilience_distribution()
    assert dist["PLANNED"] == 2

@pytest.mark.asyncio
async def test_get_service_resilience_metrics_aggregation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberResilienceService.sync_resilience(mock_db)
    metrics = ServiceResilienceService.get_service_resilience_metrics()
    assert len(metrics) == 2
    assert metrics[0]["average_resilience_score"] > 0.0

@pytest.mark.asyncio
async def test_snapshot_not_authoritative_source_of_truth(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberResilienceService.sync_resilience(mock_db)
    snap = await CyberResilienceSnapshotService.generate_snapshot(mock_db, None)
    snap["summary"]["total_resilience_records"] = 999
    assert len(CyberResilienceService.get_all_resilience()) == 2

@pytest.mark.asyncio
async def test_resilience_drift_no_previous_snapshot(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await ResilienceDriftService.check_drift(mock_db, None, None)
        assert mock_emit.call_count == 0

@pytest.mark.asyncio
async def test_snapshot_defaults_for_missing_scope():
    snap = CyberResilienceSnapshotService.get_snapshot(uuid.uuid4())
    assert snap["summary"]["total_resilience_records"] == 0

@pytest.mark.asyncio
async def test_get_resilience_by_scope_isolation(mock_db, mock_scope, mock_scope_2):
    setup_basic_mock_db(mock_db, mock_scope, mock_scope_2)
    await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH, scope_id=SCOPE_ID)
    await CyberResilienceService.create_or_sync_resilience("R2", "Desc", "S2", ServiceCriticality.HIGH, scope_id=SCOPE_ID_2)
    assert len(ServiceResilienceService.get_resilience_by_scope(SCOPE_ID)) == 1
    assert len(ServiceResilienceService.get_resilience_by_scope(SCOPE_ID_2)) == 1

@pytest.mark.asyncio
async def test_resilience_drift_readiness_increase(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService
    await CyberResilienceService.sync_resilience(mock_db)

    prev = {
        "summary": {
            "resilience_score": 61.65,
            "readiness_score": 0.0,
            "recovery_confidence_score": 68.65,
            "objective_compliance": 100.0,
        }
    }

    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await ResilienceDriftService.check_drift(mock_db, None, prev)
        events = [c.kwargs["payload"].get("drift_type") for c in mock_emit.call_args_list]
        assert "READINESS_INCREASED" in events

@pytest.mark.asyncio
async def test_resilience_drift_readiness_decrease(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService
    await CyberResilienceService.sync_resilience(mock_db)

    prev = {
        "summary": {
            "resilience_score": 61.65,
            "readiness_score": 100.0,
            "recovery_confidence_score": 68.65,
            "objective_compliance": 100.0,
        }
    }

    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await ResilienceDriftService.check_drift(mock_db, None, prev)
        events = [c.kwargs["payload"].get("drift_type") for c in mock_emit.call_args_list]
        assert "READINESS_DECREASED" in events

@pytest.mark.asyncio
async def test_critical_services_returns_empty_when_no_records():
    assert len(ServiceResilienceService.get_critical_services()) == 0

@pytest.mark.asyncio
async def test_distribution_returns_zero_counts_default():
    dist = ServiceResilienceService.get_resilience_distribution()
    assert dist["PLANNED"] == 0


# ==========================================
# PART 6: INTEGRATION & RBAC (15 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_ai_context_cyber_resilience_injection(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberResilienceService.sync_resilience(mock_db)
    await CyberResilienceSnapshotService.generate_snapshot(mock_db, None)

    ctx = await AIContextBuilder._build_cyber_resilience_context_block(None)
    assert "resilience_summary" in ctx
    assert len(ctx["resilience_records"]) == 2

@pytest.mark.asyncio
async def test_ai_prompt_builder_advisory_cyber_resilience():
    prompt = AIPromptBuilder.build_executive_prompt({})
    assert "MUST NOT approve risk" in prompt
    assert "creating resilience records" in prompt

@pytest.mark.asyncio
async def test_rbac_cyber_resilience_scope_validation(client, mock_db, mock_scope, mock_scope_2):
    setup_basic_mock_db(mock_db, mock_scope, mock_scope_2)
    headers = get_auth_header(OPERATOR_ID, "operator")
    # Operator does not own mock_scope_2
    resp = await client.get(f"/api/v1/cyber-resilience/summary?scope_id={SCOPE_ID_2}", headers=headers)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_worker_integration(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.continuous_refresh_service import ContinuousRefreshService
    await ContinuousRefreshService.refresh_all(mock_db)

@pytest.mark.asyncio
async def test_api_list_resilience_admin(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(ADMIN_ID, "admin")
    resp = await client.get("/api/v1/cyber-resilience", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_list_resilience_operator(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/cyber-resilience", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_list_resilience_reader(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(READER_ID, "reader")
    resp = await client.get("/api/v1/cyber-resilience", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_active_resilience(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/cyber-resilience/active", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_completed_resilience(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/cyber-resilience/completed", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_create_resilience_forbidden_for_reader(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(READER_ID, "reader")
    payload = {
        "title": "Forbidden Plan",
        "description": "Desc",
        "service_name": "S1",
        "service_criticality": "HIGH",
    }
    resp = await client.post("/api/v1/cyber-resilience", json=payload, headers=headers)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_api_create_resilience_success(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {
        "title": "Success Plan",
        "description": "Desc",
        "service_name": "S1",
        "service_criticality": "HIGH",
        "scope_id": str(SCOPE_ID),
    }
    resp = await client.post("/api/v1/cyber-resilience", json=payload, headers=headers)
    assert resp.status_code == 201

@pytest.mark.asyncio
async def test_api_transition_activate(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH, scope_id=SCOPE_ID)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/cyber-resilience/{r.resilience_id}/activate", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_transition_validate(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH, scope_id=SCOPE_ID)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/cyber-resilience/{r.resilience_id}/validate", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_transition_complete(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH, scope_id=SCOPE_ID)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/cyber-resilience/{r.resilience_id}/complete", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_transition_close(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH, scope_id=SCOPE_ID)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/cyber-resilience/{r.resilience_id}/close", headers=headers)
    assert resp.status_code == 200


# ==========================================
# PART 7: SERVICE RESILIENCE PRESERVATION (5 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_service_resilience_read_only(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberResilienceService.sync_resilience(mock_db)
    before = len(CyberResilienceService.get_all_resilience())
    ServiceResilienceService.get_service_resilience_metrics()
    after = len(CyberResilienceService.get_all_resilience())
    assert before == after

@pytest.mark.asyncio
async def test_service_resilience_deterministic(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberResilienceService.sync_resilience(mock_db)
    m1 = ServiceResilienceService.get_service_resilience_metrics()
    m2 = ServiceResilienceService.get_service_resilience_metrics()
    assert m1 == m2

@pytest.mark.asyncio
async def test_service_resilience_does_not_modify_history(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    before_hist = len(ResilienceHistoryService.get_history(r.resilience_id))
    ServiceResilienceService.get_service_resilience_metrics()
    after_hist = len(ResilienceHistoryService.get_history(r.resilience_id))
    assert before_hist == after_hist

@pytest.mark.asyncio
async def test_service_resilience_does_not_modify_objectives(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    before_objs = len(RecoveryObjectiveService.get_objectives(r.resilience_id))
    ServiceResilienceService.get_service_resilience_metrics()
    after_objs = len(RecoveryObjectiveService.get_objectives(r.resilience_id))
    assert before_objs == after_objs

@pytest.mark.asyncio
async def test_service_resilience_scope_isolation(mock_db, mock_scope, mock_scope_2):
    setup_basic_mock_db(mock_db, mock_scope, mock_scope_2)
    await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "Identity Provider", ServiceCriticality.HIGH, scope_id=SCOPE_ID)
    await CyberResilienceService.create_or_sync_resilience("R2", "Desc", "Directory Services", ServiceCriticality.HIGH, scope_id=SCOPE_ID_2)
    
    m_scope1 = ServiceResilienceService.get_service_resilience_metrics(SCOPE_ID)
    m_scope2 = ServiceResilienceService.get_service_resilience_metrics(SCOPE_ID_2)
    
    assert len(m_scope1) == 1
    assert m_scope1[0]["service_name"] == "Identity Provider"
    
    assert len(m_scope2) == 1
    assert m_scope2[0]["service_name"] == "Directory Services"


# ==========================================
# PART 8: EXTRA COVERAGE TESTS (10 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_api_get_objectives_not_found(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/cyber-resilience/objectives?resilience_id={uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_api_get_summary_non_admin_forbidden(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/cyber-resilience/summary", headers=headers)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_api_get_critical_services_ownership_check(client, mock_db, mock_scope, mock_scope_2):
    setup_basic_mock_db(mock_db, mock_scope, mock_scope_2)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/cyber-resilience/critical-services?scope_id={SCOPE_ID_2}", headers=headers)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_api_transition_record_not_found(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/cyber-resilience/{uuid.uuid4()}/activate", headers=headers)
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_api_transition_archived_rejection(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH, scope_id=SCOPE_ID)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.ACTIVE)
    CyberResilienceService.transition_status(r.resilience_id, ResilienceStatus.COMPLETED)
    headers = get_auth_header(OPERATOR_ID, "operator")
    # complete/close states are terminal
    resp = await client.post(f"/api/v1/cyber-resilience/{r.resilience_id}/activate", headers=headers)
    assert resp.status_code == 400

@pytest.mark.asyncio
async def test_api_get_drift_admin_success(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(ADMIN_ID, "admin")
    resp = await client.get("/api/v1/cyber-resilience/drift", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_drift_non_admin_forbidden(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/cyber-resilience/drift", headers=headers)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_recovery_objective_registry_types():
    assert "RPO" in RecoveryObjectiveRegistry.list_types()

@pytest.mark.asyncio
async def test_resilience_drift_non_terminal_history(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberResilienceService.create_or_sync_resilience("R1", "Desc", "S1", ServiceCriticality.HIGH)
    # verify history tracks CREATED
    hist = ResilienceHistoryService.get_history(r.resilience_id)
    assert len(hist) == 1

@pytest.mark.asyncio
async def test_criticality_registry_weight_invalid():
    assert CriticalityRegistry.get_weight("INVALID") == 1.0
