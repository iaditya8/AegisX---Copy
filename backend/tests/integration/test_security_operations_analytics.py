import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from src.core.security import create_access_token
from src.domain.entities.security_operations_analytics import (
    AnalyticsStatus,
    AnalyticsSeverity,
    KPIStatus,
    KRIStatus,
    AnalyticsResponse,
    AnalystPerformanceResponse,
    OperationalKPIResponse,
    OperationalKRIResponse,
)
from src.infrastructure.database.models import Scope, User
from src.services.soc_kpi_registry import SOCKPIRegistry
from src.services.soc_kri_registry import SOCKRIRegistry
from src.services.analyst_role_registry import AnalystRoleRegistry
from src.services.analytics_fingerprint_service import AnalyticsFingerprintService
from src.services.analytics_history_service import AnalyticsHistoryService
from src.services.analyst_performance_service import AnalystPerformanceService
from src.services.queue_analytics_service import QueueAnalyticsService
from src.services.operational_kpi_service import OperationalKPIService
from src.services.operational_kri_service import OperationalKRIService
from src.services.soc_drift_service import SOCDriftService
from src.services.security_operations_analytics_service import SecurityOperationsAnalyticsService
from src.services.soc_snapshot_service import SOCSnapshotService
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
    SecurityOperationsAnalyticsService.clear_analytics()
    AnalystPerformanceService.clear_analysts()
    OperationalKPIService.clear_kpis()
    OperationalKRIService.clear_kris()
    AnalyticsHistoryService.clear_history()
    SOCSnapshotService.clear_snapshots()


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
        else:
            mock_result.scalars().all = MagicMock(return_value=[])
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
        return mock_result

    mock_db.execute = AsyncMock(side_effect=mock_execute)


# ==========================================
# PART 1: REGISTRIES & FINGERPRINT (15 Tests)
# ==========================================

def test_kpi_registry_list():
    assert "Mean Time To Detect (MTTD)" in SOCKPIRegistry.list_types()

def test_kpi_registry_validate():
    assert SOCKPIRegistry.validate("Mean Time To Detect (MTTD)")
    assert not SOCKPIRegistry.validate("INVALID")

def test_kri_registry_list():
    assert "Alert Backlog Growth" in SOCKRIRegistry.list_types()

def test_kri_registry_validate():
    assert SOCKRIRegistry.validate("Alert Backlog Growth")
    assert not SOCKRIRegistry.validate("INVALID")

def test_role_registry_list():
    assert "TIER1_ANALYST" in AnalystRoleRegistry.list_roles()

def test_role_registry_validate():
    assert AnalystRoleRegistry.validate("TIER1_ANALYST")
    assert not AnalystRoleRegistry.validate("INVALID")

def test_analytics_fingerprint_generation():
    f = AnalyticsFingerprintService.generate_fingerprint("name", SCOPE_ID)
    assert isinstance(f, str) and len(f) == 64

def test_analytics_fingerprint_stability():
    f1 = AnalyticsFingerprintService.generate_fingerprint("name", SCOPE_ID)
    f2 = AnalyticsFingerprintService.generate_fingerprint("name", SCOPE_ID)
    assert f1 == f2

def test_analytics_fingerprint_case_insensitivity():
    f1 = AnalyticsFingerprintService.generate_fingerprint("Name", SCOPE_ID)
    f2 = AnalyticsFingerprintService.generate_fingerprint("name", SCOPE_ID)
    assert f1 == f2

def test_analytics_fingerprint_changes_on_name():
    f1 = AnalyticsFingerprintService.generate_fingerprint("name 1", SCOPE_ID)
    f2 = AnalyticsFingerprintService.generate_fingerprint("name 2", SCOPE_ID)
    assert f1 != f2

def test_analytics_fingerprint_changes_on_scope():
    f1 = AnalyticsFingerprintService.generate_fingerprint("name", SCOPE_ID)
    f2 = AnalyticsFingerprintService.generate_fingerprint("name", SCOPE_ID_2)
    assert f1 != f2

def test_kpi_registry_count():
    assert len(SOCKPIRegistry.list_types()) == 9

def test_kri_registry_count():
    assert len(SOCKRIRegistry.list_types()) == 6

def test_role_registry_count():
    assert len(AnalystRoleRegistry.list_roles()) == 6

def test_role_registry_strip():
    assert AnalystRoleRegistry.validate("  TIER1_ANALYST  ")


# ==========================================
# PART 2: LIFECYCLE & IDENTITY (20 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_create_analytics(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    assert r.status == AnalyticsStatus.ACTIVE

@pytest.mark.asyncio
async def test_transition_active_to_review(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    r_trans = SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.REVIEW)
    assert r_trans.status == AnalyticsStatus.REVIEW

@pytest.mark.asyncio
async def test_transition_active_to_completed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    r_trans = SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.COMPLETED)
    assert r_trans.status == AnalyticsStatus.COMPLETED

@pytest.mark.asyncio
async def test_transition_active_to_archived(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    r_trans = SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.ARCHIVED)
    assert r_trans.status == AnalyticsStatus.ARCHIVED

@pytest.mark.asyncio
async def test_terminal_state_archived(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.ARCHIVED)
    # Re-transitioning should fail/leave status as ARCHIVED
    res = SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.ACTIVE)
    assert res.status == AnalyticsStatus.ARCHIVED

@pytest.mark.asyncio
async def test_sync_analytics(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    synced = await SecurityOperationsAnalyticsService.sync_analytics(mock_db)
    assert len(synced) == 1

@pytest.mark.asyncio
async def test_identity_preservation_sync_analytics(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r1 = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc 1")
    r2 = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc 2")
    assert r1.analytics_id == r2.analytics_id

@pytest.mark.asyncio
async def test_invalid_lifecycle_transition_review_to_active(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.REVIEW)
    with pytest.raises(ValueError, match="Invalid transition"):
        SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.ACTIVE)

@pytest.mark.asyncio
async def test_invalid_lifecycle_transition_completed_to_review(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.COMPLETED)
    with pytest.raises(ValueError, match="Invalid transition"):
        SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.REVIEW)

@pytest.mark.asyncio
async def test_duplicate_prevention_on_creation_analytics(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r1 = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    r2 = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    assert len(SecurityOperationsAnalyticsService.get_all_analytics()) == 1

@pytest.mark.asyncio
async def test_get_analytics_not_found():
    assert SecurityOperationsAnalyticsService.get_analytics(uuid.uuid4()) == None

@pytest.mark.asyncio
async def test_sync_does_not_reactivate_archived(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("SOC Queue Health Alert Thresholds", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.ARCHIVED)
    await SecurityOperationsAnalyticsService.sync_analytics(mock_db)
    assert r.status == AnalyticsStatus.ARCHIVED

@pytest.mark.asyncio
async def test_transition_status_record_not_found_analytics():
    with pytest.raises(ValueError, match="not found"):
        SecurityOperationsAnalyticsService.transition_status(uuid.uuid4(), AnalyticsStatus.ACTIVE)

@pytest.mark.asyncio
async def test_transition_review_to_completed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.REVIEW)
    res = SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.COMPLETED)
    assert res.status == AnalyticsStatus.COMPLETED

@pytest.mark.asyncio
async def test_transition_review_to_archived(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.REVIEW)
    res = SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.ARCHIVED)
    assert res.status == AnalyticsStatus.ARCHIVED

@pytest.mark.asyncio
async def test_transition_completed_to_archived(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.COMPLETED)
    res = SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.ARCHIVED)
    assert res.status == AnalyticsStatus.ARCHIVED

@pytest.mark.asyncio
async def test_get_all_analytics_empty():
    assert len(SecurityOperationsAnalyticsService.get_all_analytics()) == 0

@pytest.mark.asyncio
async def test_get_analytics_by_fingerprint_not_found():
    assert SecurityOperationsAnalyticsService.get_analytics_by_fingerprint("nonexistent") == None

@pytest.mark.asyncio
async def test_to_response_mapping(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    resp = SecurityOperationsAnalyticsService.to_response(r)
    assert resp.analytics_name == "A1"


# ==========================================
# PART 3: HISTORY & AUDIT (15 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_analytics_history_recorded(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    hist = AnalyticsHistoryService.get_history(r.analytics_id)
    assert len(hist) > 0
    assert hist[0].event_type == "CREATED"

@pytest.mark.asyncio
async def test_analytics_history_immutable(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    hist = AnalyticsHistoryService.get_history(r.analytics_id)
    hist.clear()
    assert len(AnalyticsHistoryService.get_history(r.analytics_id)) == 1

@pytest.mark.asyncio
async def test_analytics_history_on_review(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.REVIEW)
    hist = AnalyticsHistoryService.get_history(r.analytics_id)
    event_types = [h.event_type for h in hist]
    assert "REVIEWED" in event_types

@pytest.mark.asyncio
async def test_analytics_history_on_completion(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.COMPLETED)
    hist = AnalyticsHistoryService.get_history(r.analytics_id)
    event_types = [h.event_type for h in hist]
    assert "COMPLETED" in event_types

@pytest.mark.asyncio
async def test_analytics_history_on_archive(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.ARCHIVED)
    hist = AnalyticsHistoryService.get_history(r.analytics_id)
    event_types = [h.event_type for h in hist]
    assert "ARCHIVED" in event_types

@pytest.mark.asyncio
async def test_analytics_history_ordering(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.REVIEW)
    hist = AnalyticsHistoryService.get_history(r.analytics_id)
    assert hist[0].timestamp <= hist[1].timestamp

@pytest.mark.asyncio
async def test_history_survives_soc_snapshot_rebuild(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    await SOCSnapshotService.generate_snapshot(mock_db, None)
    assert len(AnalyticsHistoryService.get_history(r.analytics_id)) == 1

@pytest.mark.asyncio
async def test_analytics_history_clear(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    AnalyticsHistoryService.clear_history()
    assert len(AnalyticsHistoryService.get_history(r.analytics_id)) == 0

@pytest.mark.asyncio
async def test_analytics_history_record_event_directly(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    AnalyticsHistoryService.record_event(r.analytics_id, "TEST_EVENT", "details")
    hist = AnalyticsHistoryService.get_history(r.analytics_id)
    assert hist[-1].event_type == "TEST_EVENT"

@pytest.mark.asyncio
async def test_analytics_history_order_preserved_on_multiple_events(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    AnalyticsHistoryService.record_event(r.analytics_id, "EVENT_1", "1")
    AnalyticsHistoryService.record_event(r.analytics_id, "EVENT_2", "2")
    hist = AnalyticsHistoryService.get_history(r.analytics_id)
    assert hist[1].event_type == "EVENT_1"
    assert hist[2].event_type == "EVENT_2"

@pytest.mark.asyncio
async def test_analytics_history_empty_for_invalid_id():
    assert len(AnalyticsHistoryService.get_history(uuid.uuid4())) == 0

@pytest.mark.asyncio
async def test_analytics_history_entry_properties(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    hist = AnalyticsHistoryService.get_history(r.analytics_id)
    assert hist[0].analytics_id == r.analytics_id
    assert isinstance(hist[0].timestamp, datetime)

@pytest.mark.asyncio
async def test_analytics_history_entry_frozen(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    hist = AnalyticsHistoryService.get_history(r.analytics_id)
    with pytest.raises(Exception):
        hist[0].event_type = "MUTATED"

@pytest.mark.asyncio
async def test_analytics_history_deep_copy_isolation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    hist1 = AnalyticsHistoryService.get_history(r.analytics_id)
    hist2 = AnalyticsHistoryService.get_history(r.analytics_id)
    assert hist1 is not hist2


# ==========================================
# PART 4: KPI & KRI CALCULATION (15 Tests)
# ==========================================

def test_set_kpi():
    k = OperationalKPIService.set_kpi("Mean Time To Detect (MTTD)", 5.0, 10.0)
    assert k.current_value == 5.0

def test_set_kpi_invalid_name():
    with pytest.raises(ValueError, match="Invalid KPI"):
        OperationalKPIService.set_kpi("INVALID_KPI", 5.0, 10.0)

def test_calculate_kpi_on_target():
    k = OperationalKPIService.set_kpi("Mean Time To Detect (MTTD)", 5.0, 10.0)
    assert k.status == KPIStatus.ON_TARGET

def test_calculate_kpi_at_risk():
    k = OperationalKPIService.set_kpi("Mean Time To Detect (MTTD)", 12.0, 10.0)
    assert k.status == KPIStatus.AT_RISK

def test_calculate_kpi_off_target():
    k = OperationalKPIService.set_kpi("Mean Time To Detect (MTTD)", 25.0, 10.0)
    assert k.status == KPIStatus.OFF_TARGET

def test_calculate_kpi_rate_on_target():
    k = OperationalKPIService.set_kpi("Alert Closure Rate", 95.0, 90.0)
    assert k.status == KPIStatus.ON_TARGET

def test_calculate_kpi_rate_at_risk():
    k = OperationalKPIService.set_kpi("Alert Closure Rate", 80.0, 90.0)
    assert k.status == KPIStatus.AT_RISK

def test_calculate_kpi_rate_off_target():
    k = OperationalKPIService.set_kpi("Alert Closure Rate", 50.0, 90.0)
    assert k.status == KPIStatus.OFF_TARGET

def test_set_kri():
    k = OperationalKRIService.set_kri("Alert Backlog Growth", 2.0, 5.0)
    assert k.current_value == 2.0

def test_set_kri_invalid_name():
    with pytest.raises(ValueError, match="Invalid KRI"):
        OperationalKRIService.set_kri("INVALID_KRI", 2.0, 5.0)

def test_calculate_kri_low_risk():
    k = OperationalKRIService.set_kri("Alert Backlog Growth", 1.0, 5.0)
    assert k.status == KRIStatus.LOW_RISK

def test_calculate_kri_medium_risk():
    k = OperationalKRIService.set_kri("Alert Backlog Growth", 4.0, 5.0)
    assert k.status == KRIStatus.MEDIUM_RISK

def test_calculate_kri_high_risk():
    k = OperationalKRIService.set_kri("Alert Backlog Growth", 6.0, 5.0)
    assert k.status == KRIStatus.HIGH_RISK

def test_calculate_kri_critical_risk():
    k = OperationalKRIService.set_kri("Alert Backlog Growth", 10.0, 5.0)
    assert k.status == KRIStatus.CRITICAL_RISK

def test_clear_kpis_kris():
    OperationalKPIService.set_kpi("Mean Time To Detect (MTTD)", 5.0, 10.0)
    OperationalKRIService.set_kri("Alert Backlog Growth", 2.0, 5.0)
    OperationalKPIService.clear_kpis()
    OperationalKRIService.clear_kris()
    assert len(OperationalKPIService.get_kpis()) == 9 # seeds back
    assert len(OperationalKRIService.get_kris()) == 6 # seeds back


# ==========================================
# PART 5: SNAPSHOT & DRIFT (15 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_generate_soc_snapshot(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityOperationsAnalyticsService.sync_analytics(mock_db)
    snap = await SOCSnapshotService.generate_snapshot(mock_db, None)
    assert snap["summary"]["total_analytics_records"] == 1

@pytest.mark.asyncio
async def test_soc_snapshot_cache_clear(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SOCSnapshotService.generate_snapshot(mock_db, None)
    SOCSnapshotService.clear_snapshots()
    snap = SOCSnapshotService.get_snapshot(None)
    assert snap["summary"]["total_analytics_records"] == 0

@pytest.mark.asyncio
async def test_soc_snapshot_corruption_rebuild(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityOperationsAnalyticsService.sync_analytics(mock_db)
    SOCSnapshotService._snapshots[None] = "CORRUPTED"
    snap = SOCSnapshotService.get_snapshot(None)
    assert snap["summary"]["total_analytics_records"] == 0
    await SOCSnapshotService.generate_snapshot(mock_db, None)
    assert SOCSnapshotService.get_snapshot(None)["summary"]["total_analytics_records"] == 1

@pytest.mark.asyncio
async def test_soc_drift_detected_degraded(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    prev = {
        "summary": {
            "operational_health_score": 100.0,
            "queue_size": 24,
            "queue_efficiency": 94.5,
            "average_analyst_score": 90.0,
        }
    }

    await SecurityOperationsAnalyticsService.sync_analytics(mock_db)

    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await SOCDriftService.process_drift(mock_db, None, prev)
        events = [c.kwargs["payload"].get("drift_type") for c in mock_emit.call_args_list if "drift_type" in c.kwargs["payload"]]
        assert "PERFORMANCE_DEGRADED" in events

@pytest.mark.asyncio
async def test_soc_drift_detected_improved(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    prev = {
        "summary": {
            "operational_health_score": 0.0,
            "queue_size": 24,
            "queue_efficiency": 94.5,
            "average_analyst_score": 0.0,
        }
    }

    await SecurityOperationsAnalyticsService.sync_analytics(mock_db)

    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await SOCDriftService.process_drift(mock_db, None, prev)
        events = [c.kwargs["payload"].get("drift_type") for c in mock_emit.call_args_list if "drift_type" in c.kwargs["payload"]]
        assert "PERFORMANCE_IMPROVED" in events

@pytest.mark.asyncio
async def test_soc_drift_efficiency_changed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    prev = {
        "summary": {
            "operational_health_score": 94.75,
            "queue_size": 24,
            "queue_efficiency": 0.0,
            "average_analyst_score": 95.0,
        }
    }

    await SecurityOperationsAnalyticsService.sync_analytics(mock_db)

    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await SOCDriftService.process_drift(mock_db, None, prev)
        metrics = [c.kwargs["payload"].get("metric") for c in mock_emit.call_args_list if "metric" in c.kwargs["payload"]]
        assert "queue_efficiency" in metrics

@pytest.mark.asyncio
async def test_soc_drift_no_previous_snapshot(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService
    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await SOCDriftService.process_drift(mock_db, None, None)
        assert mock_emit.call_count == 0

@pytest.mark.asyncio
async def test_soc_snapshot_defaults_for_missing_scope():
    snap = SOCSnapshotService.get_snapshot(uuid.uuid4())
    assert snap["summary"]["total_analytics_records"] == 0

@pytest.mark.asyncio
async def test_soc_snapshot_not_authoritative(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityOperationsAnalyticsService.sync_analytics(mock_db)
    snap = await SOCSnapshotService.generate_snapshot(mock_db, None)
    snap["summary"]["total_analytics_records"] = 999
    assert len(SecurityOperationsAnalyticsService.get_all_analytics()) == 1


# ==========================================
# PART 6: RBAC & ROUTER (15 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_rbac_soc_scope_validation(client, mock_db, mock_scope, mock_scope_2):
    setup_basic_mock_db(mock_db, mock_scope, mock_scope_2)
    headers = get_auth_header(OPERATOR_ID, "operator")
    # Operator does not own mock_scope_2
    resp = await client.get(f"/api/v1/security-operations-analytics/summary?scope_id={SCOPE_ID_2}", headers=headers)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_api_list_analytics_admin(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(ADMIN_ID, "admin")
    resp = await client.get("/api/v1/security-operations-analytics", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_list_analytics_operator(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-operations-analytics", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_create_analytics_reader_forbidden(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(READER_ID, "reader")
    payload = {"analytics_name": "Plan", "description": "Desc"}
    resp = await client.post("/api/v1/security-operations-analytics", json=payload, headers=headers)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_api_create_analytics_success(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {"analytics_name": "Plan", "description": "Desc", "scope_id": str(SCOPE_ID)}
    resp = await client.post("/api/v1/security-operations-analytics", json=payload, headers=headers)
    assert resp.status_code == 201

@pytest.mark.asyncio
async def test_api_get_active_analytics(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-operations-analytics/analytics/active", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_archived_analytics(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-operations-analytics/analytics/archived", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_single_analytics(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc", scope_id=SCOPE_ID)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/security-operations-analytics/analytics/{r.analytics_id}", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_list_analysts(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-operations-analytics/analysts", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_analyst_rankings(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-operations-analytics/analysts/rankings", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_queues(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-operations-analytics/queues", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_queues_backlog(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-operations-analytics/queues/backlog", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_kpis(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-operations-analytics/kpis", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_kris(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-operations-analytics/kris", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_drift_admin(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(ADMIN_ID, "admin")
    resp = await client.get("/api/v1/security-operations-analytics/drift", headers=headers)
    assert resp.status_code == 200


# ==========================================
# PART 7: MANDATORY COMPLETION & PRESERVATION (10 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_completed_analytics_not_reactivated_by_sync(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("SOC Queue Health Alert Thresholds", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.COMPLETED)
    await SecurityOperationsAnalyticsService.sync_analytics(mock_db)
    assert r.status == AnalyticsStatus.COMPLETED

@pytest.mark.asyncio
async def test_completed_analytics_not_reactivated_by_worker(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("SOC Queue Health Alert Thresholds", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.COMPLETED)
    
    from src.services.continuous_refresh_service import ContinuousRefreshService
    await ContinuousRefreshService.refresh_all(mock_db)
    assert r.status == AnalyticsStatus.COMPLETED

@pytest.mark.asyncio
async def test_completed_analytics_not_reactivated_by_kpi_refresh(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.COMPLETED)
    OperationalKPIService.calculate()
    assert r.status == AnalyticsStatus.COMPLETED

@pytest.mark.asyncio
async def test_completed_analytics_not_reactivated_by_kri_refresh(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.COMPLETED)
    OperationalKRIService.calculate()
    assert r.status == AnalyticsStatus.COMPLETED

@pytest.mark.asyncio
async def test_analyst_ranking_stability():
    # Rank order is Bob then Alice? Or Alice then Bob based on score
    # Alice score = 150*0.4 + 12*2 + 5*5 = 109 -> raw_score = 100 - (5.2*0.8 + 22.4*0.4) + 109*0.3 = 100 - 13.12 + 32.7 = 119.58 -> score = 100
    # Bob score = 90*0.4 + 8*2 + 4*5 = 72 -> raw_score = 100 - (12.5*0.8 + 45.2*0.4) + 72*0.3 = 100 - 28.08 + 21.6 = 93.52 -> score = 93.52
    r = AnalystPerformanceService.get_rankings()
    assert r[0].analyst_name == "Alice Vance"
    assert r[1].analyst_name == "Bob Smith"

@pytest.mark.asyncio
async def test_queue_metrics_deterministic():
    s1 = QueueAnalyticsService.get_queue_summary()
    s2 = QueueAnalyticsService.get_queue_summary()
    assert s1 == s2

@pytest.mark.asyncio
async def test_snapshot_identity_preserved_after_rebuild(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityOperationsAnalyticsService.sync_analytics(mock_db)
    snap1 = await SOCSnapshotService.generate_snapshot(mock_db, None)
    SOCSnapshotService.clear_snapshots()
    snap2 = await SOCSnapshotService.generate_snapshot(mock_db, None)
    assert snap1["summary"]["total_analytics_records"] == snap2["summary"]["total_analytics_records"]

@pytest.mark.asyncio
async def test_analytics_history_survives_worker_refresh(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc")
    
    from src.services.continuous_refresh_service import ContinuousRefreshService
    await ContinuousRefreshService.refresh_all(mock_db)
    
    hist = AnalyticsHistoryService.get_history(r.analytics_id)
    assert len(hist) > 0


# ==========================================
# PART 8: EXTRA INTEGRATION TESTS (10 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_ai_context_soc_injection(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityOperationsAnalyticsService.sync_analytics(mock_db)
    await SOCSnapshotService.generate_snapshot(mock_db, None)

    ctx = await AIContextBuilder._build_soc_context_block(None)
    assert "analyst_performance_summary" in ctx
    assert len(ctx["soc_analytics_records"]) == 1

@pytest.mark.asyncio
async def test_ai_prompt_builder_advisory_soc():
    prompt = AIPromptBuilder.build_executive_prompt({})
    assert "MUST NOT approve risk" in prompt
    assert "creating analytics" in prompt

@pytest.mark.asyncio
async def test_api_transition_review(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc", scope_id=SCOPE_ID)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-operations-analytics/analytics/{r.analytics_id}/review", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_transition_archive(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc", scope_id=SCOPE_ID)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-operations-analytics/analytics/{r.analytics_id}/archive", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_transition_review_archived_rejection(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc", scope_id=SCOPE_ID)
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.ARCHIVED)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-operations-analytics/analytics/{r.analytics_id}/review", headers=headers)
    assert resp.status_code == 400

@pytest.mark.asyncio
async def test_api_transition_archive_archived_rejection(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityOperationsAnalyticsService.create_or_sync_analytics("A1", "Desc", scope_id=SCOPE_ID)
    SecurityOperationsAnalyticsService.transition_status(r.analytics_id, AnalyticsStatus.ARCHIVED)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-operations-analytics/analytics/{r.analytics_id}/archive", headers=headers)
    assert resp.status_code == 400

@pytest.mark.asyncio
async def test_api_transition_record_not_found_review(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-operations-analytics/analytics/{uuid.uuid4()}/review", headers=headers)
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_api_transition_record_not_found_archive(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-operations-analytics/analytics/{uuid.uuid4()}/archive", headers=headers)
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_api_get_single_analytics_not_found(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/security-operations-analytics/analytics/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_api_get_summary_non_admin_forbidden(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-operations-analytics/summary", headers=headers)
    assert resp.status_code == 403
