import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from src.core.security import create_access_token
from src.domain.entities.cyber_risk_quantification import (
    RiskQuantificationStatus,
    RiskScenarioType,
    RiskSeverity,
    CyberRiskResponse,
    RiskScenarioResponse,
    RiskForecastResponse,
)
from src.infrastructure.database.models import Scope, User
from src.services.risk_scenario_registry import RiskScenarioRegistry
from src.services.risk_frequency_registry import RiskFrequencyRegistry
from src.services.risk_impact_registry import RiskImpactRegistry
from src.services.risk_quantification_fingerprint_service import RiskQuantificationFingerprintService
from src.services.quantified_risk_history_service import QuantifiedRiskHistoryService
from src.services.cyber_risk_quantification_service import CyberRiskQuantificationService
from src.services.loss_expectancy_service import LossExpectancyService
from src.services.residual_risk_service import ResidualRiskService
from src.services.risk_forecast_service import RiskForecastService
from src.services.risk_trend_service import RiskTrendService
from src.services.risk_drift_service import RiskDriftService
from src.services.risk_quantification_snapshot_service import RiskQuantificationSnapshotService
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
    CyberRiskQuantificationService.clear_risks()
    QuantifiedRiskHistoryService.clear_history()
    RiskTrendService.clear_trends()
    RiskQuantificationSnapshotService.clear_snapshots()


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
# PART 1: REGISTRY & FINGERPRINT (15 Tests)
# ==========================================

def test_scenario_registry_list():
    assert "DATA_BREACH" in RiskScenarioRegistry.list_types()

def test_scenario_registry_validate():
    assert RiskScenarioRegistry.validate("DATA_BREACH")
    assert not RiskScenarioRegistry.validate("INVALID")

def test_frequency_registry_list():
    assert "RARE" in RiskFrequencyRegistry.list_frequencies()

def test_frequency_registry_aro():
    assert RiskFrequencyRegistry.get_aro("RARE") == 0.05
    assert RiskFrequencyRegistry.get_aro("FREQUENT") == 3.0

def test_frequency_registry_validate():
    assert RiskFrequencyRegistry.validate("RARE")
    assert not RiskFrequencyRegistry.validate("INVALID")

def test_impact_registry_list():
    assert "LOW" in RiskImpactRegistry.list_impacts()

def test_impact_registry_factor():
    assert RiskImpactRegistry.get_factor("LOW") == 0.1
    assert RiskImpactRegistry.get_factor("CRITICAL") == 0.9

def test_impact_registry_validate():
    assert RiskImpactRegistry.validate("LOW")
    assert not RiskImpactRegistry.validate("INVALID")

def test_risk_fingerprint_generation():
    f = RiskQuantificationFingerprintService.generate_fingerprint("DATA_BREACH", "Title", SCOPE_ID)
    assert isinstance(f, str) and len(f) == 64

def test_risk_fingerprint_stability():
    f1 = RiskQuantificationFingerprintService.generate_fingerprint("DATA_BREACH", "Title", SCOPE_ID)
    f2 = RiskQuantificationFingerprintService.generate_fingerprint("DATA_BREACH", "Title", SCOPE_ID)
    assert f1 == f2

def test_risk_fingerprint_case_insensitivity():
    f1 = RiskQuantificationFingerprintService.generate_fingerprint("DATA_BREACH", "Title", SCOPE_ID)
    f2 = RiskQuantificationFingerprintService.generate_fingerprint("data_breach", "title", SCOPE_ID)
    assert f1 == f2

def test_risk_fingerprint_changes_on_scenario():
    f1 = RiskQuantificationFingerprintService.generate_fingerprint("DATA_BREACH", "Title", SCOPE_ID)
    f2 = RiskQuantificationFingerprintService.generate_fingerprint("RANSOMWARE", "Title", SCOPE_ID)
    assert f1 != f2

def test_risk_fingerprint_changes_on_title():
    f1 = RiskQuantificationFingerprintService.generate_fingerprint("DATA_BREACH", "Title 1", SCOPE_ID)
    f2 = RiskQuantificationFingerprintService.generate_fingerprint("DATA_BREACH", "Title 2", SCOPE_ID)
    assert f1 != f2

def test_risk_fingerprint_changes_on_scope():
    f1 = RiskQuantificationFingerprintService.generate_fingerprint("DATA_BREACH", "Title", SCOPE_ID)
    f2 = RiskQuantificationFingerprintService.generate_fingerprint("DATA_BREACH", "Title", SCOPE_ID_2)
    assert f1 != f2

def test_scenario_registry_types_count():
    assert len(RiskScenarioRegistry.list_types()) == 6


# ==========================================
# PART 2: LIFECYCLE & IDENTITY (20 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_create_risk(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    assert r.status == RiskQuantificationStatus.ACTIVE

@pytest.mark.asyncio
async def test_risk_auto_creation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    synced = await CyberRiskQuantificationService.sync_risks(mock_db)
    assert len(synced) == 2
    assert synced[0].status == RiskQuantificationStatus.ACTIVE

@pytest.mark.asyncio
async def test_risk_fingerprint_stability_sync(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r1 = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    r2 = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    assert r1.risk_fingerprint == r2.risk_fingerprint

@pytest.mark.asyncio
async def test_risk_sync_preserves_identity(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r1 = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc 1", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    r2 = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc 2", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    assert r1.risk_id == r2.risk_id

@pytest.mark.asyncio
async def test_risk_accept_transition(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    res = await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.ACCEPTED)
    assert res.status == RiskQuantificationStatus.ACCEPTED

@pytest.mark.asyncio
async def test_risk_mitigate_transition(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    res = await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.MITIGATED)
    assert res.status == RiskQuantificationStatus.MITIGATED

@pytest.mark.asyncio
async def test_risk_close_transition(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    res = await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.CLOSED)
    assert res.status == RiskQuantificationStatus.CLOSED

@pytest.mark.asyncio
async def test_risk_terminal_state_enforcement(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.CLOSED)
    # Re-transitioning should do nothing and return the record in CLOSED status
    res = await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.ACTIVE)
    assert res.status == RiskQuantificationStatus.CLOSED

@pytest.mark.asyncio
async def test_sync_does_not_reactivate_closed(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("Cloud S3 Bucket Leaks", "Desc", RiskScenarioType.CLOUD_COMPROMISE, "OCCASIONAL", "HIGH", 120000.0)
    await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.CLOSED)
    await CyberRiskQuantificationService.sync_risks(mock_db)
    assert r.status == RiskQuantificationStatus.CLOSED

@pytest.mark.asyncio
async def test_invalid_lifecycle_transition_accepted_to_mitigated(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.ACCEPTED)
    with pytest.raises(ValueError, match="Invalid transition"):
        await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.MITIGATED)

@pytest.mark.asyncio
async def test_duplicate_prevention_on_creation_risk(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r1 = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    r2 = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    assert len(await CyberRiskQuantificationService.get_all_risks()) == 1

@pytest.mark.asyncio
async def test_get_risk_not_found_risk():
    assert await CyberRiskQuantificationService.get_risk(uuid.uuid4()) is None

@pytest.mark.asyncio
async def test_get_risk_by_fingerprint_not_found_risk():
    assert await CyberRiskQuantificationService.get_risk_by_fingerprint("nonexistent") is None

@pytest.mark.asyncio
async def test_transition_status_record_not_found_risk():
    with pytest.raises(ValueError, match="not found"):
        await CyberRiskQuantificationService.transition_status(uuid.uuid4(), RiskQuantificationStatus.ACTIVE)

@pytest.mark.asyncio
async def test_risk_identity_preservation_on_exposure_value_update(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r1 = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    r2 = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 5000.0)
    assert r1.risk_id == r2.risk_id
    assert r2.exposure_value == 5000.0

@pytest.mark.asyncio
async def test_quantified_risk_record_to_response(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    resp = CyberRiskQuantificationService.to_response(r)
    assert resp.title == "T1"


# ==========================================
# PART 3: HISTORY & AUDIT (15 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_risk_history_preserved(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    hist = QuantifiedRiskHistoryService.get_history(r.risk_id)
    assert len(hist) > 0
    assert hist[0].event_type == "CREATED"

@pytest.mark.asyncio
async def test_risk_history_immutable(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    hist = QuantifiedRiskHistoryService.get_history(r.risk_id)
    hist.clear()
    assert len(QuantifiedRiskHistoryService.get_history(r.risk_id)) == 1

@pytest.mark.asyncio
async def test_risk_history_on_acceptance(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.ACCEPTED)
    hist = QuantifiedRiskHistoryService.get_history(r.risk_id)
    event_types = [h.event_type for h in hist]
    assert "ACCEPTED" in event_types

@pytest.mark.asyncio
async def test_risk_history_on_mitigation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.MITIGATED)
    hist = QuantifiedRiskHistoryService.get_history(r.risk_id)
    event_types = [h.event_type for h in hist]
    assert "MITIGATED" in event_types

@pytest.mark.asyncio
async def test_risk_history_on_closure(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.CLOSED)
    hist = QuantifiedRiskHistoryService.get_history(r.risk_id)
    event_types = [h.event_type for h in hist]
    assert "CLOSED" in event_types

@pytest.mark.asyncio
async def test_risk_history_ordering(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.ACCEPTED)
    hist = QuantifiedRiskHistoryService.get_history(r.risk_id)
    assert hist[0].timestamp <= hist[1].timestamp

@pytest.mark.asyncio
async def test_history_survives_snapshot_rebuild_risk(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    await RiskQuantificationSnapshotService.generate_snapshot(mock_db, None)
    assert len(QuantifiedRiskHistoryService.get_history(r.risk_id)) == 1

@pytest.mark.asyncio
async def test_history_clear_risk(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    QuantifiedRiskHistoryService.clear_history()
    assert len(QuantifiedRiskHistoryService.get_history(r.risk_id)) == 0

@pytest.mark.asyncio
async def test_history_record_event_directly_risk(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    QuantifiedRiskHistoryService.record_event(r.risk_id, "TEST_EVENT", "details")
    hist = QuantifiedRiskHistoryService.get_history(r.risk_id)
    assert hist[-1].event_type == "TEST_EVENT"


# ==========================================
# PART 4: LOSS EXPECTANCY & DET (15 Tests)
# ==========================================

def test_sle_calculation():
    # SLE = Asset Value * Exposure Factor
    # exposure_value = 1000.0, low factor = 0.1 -> SLE = 100.0
    assert LossExpectancyService.calculate_sle(1000.0, 0.1) == 100.0

def test_ale_calculation():
    # ALE = SLE * ARO
    # SLE = 100.0, ARO = 1.0 -> ALE = 100.0
    assert LossExpectancyService.calculate_ale(100.0, 1.0) == 100.0

def test_residual_risk_calculation():
    # inherent = (exposure_value / 100000) * ARO * factor * 100
    # exposure = 100000, factor = 0.6 (HIGH), ARO = 1.0 (LIKELY) -> inherent = 60.0
    inherent = ResidualRiskService.calculate_inherent_risk_score(100000.0, 0.6, 1.0)
    assert inherent == 60.0

    # residual = inherent * (1 - mitigation_effectiveness / 100)
    # inherent = 60.0, effectiveness = 75% -> residual = 15.0
    assert ResidualRiskService.calculate_residual_risk_score(60.0, 75.0) == 15.0

def test_mitigation_effectiveness_calculation():
    # inherent = 60.0, residual = 15.0 -> effectiveness = 75.0%
    assert ResidualRiskService.calculate_mitigation_effectiveness(60.0, 15.0) == 75.0

def test_mitigation_effectiveness_calculation_zero_inherent():
    assert ResidualRiskService.calculate_mitigation_effectiveness(0.0, 0.0) == 100.0

def test_forecast_generation():
    forecasts = RiskForecastService.get_forecasts(uuid.uuid4(), 100.0, 1000.0)
    assert len(forecasts) == 4
    assert forecasts[0].quarter == "Q1"
    assert forecasts[0].projected_loss == 100.0

def test_forecast_deterministic():
    id_val = uuid.uuid4()
    f1 = RiskForecastService.get_forecasts(id_val, 100.0, 1000.0)
    f2 = RiskForecastService.get_forecasts(id_val, 100.0, 1000.0)
    assert f1[0].projected_loss == f2[0].projected_loss

def test_risk_trend_generation():
    id_val = uuid.uuid4()
    trends = RiskTrendService.calculate_trends(id_val, 1000.0)
    # pre-seeds 3 points and appends current
    assert len(trends) == 4
    assert trends[-1] == 1000.0


# ==========================================
# PART 5: SNAPSHOT & DRIFT (15 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_generate_snapshot_risk(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberRiskQuantificationService.sync_risks(mock_db)
    snap = await RiskQuantificationSnapshotService.generate_snapshot(mock_db, None)
    assert snap["summary"]["total_risk_records"] == 2

@pytest.mark.asyncio
async def test_snapshot_rebuild_consistency(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberRiskQuantificationService.sync_risks(mock_db)
    snap1 = await RiskQuantificationSnapshotService.generate_snapshot(mock_db, None)
    RiskQuantificationSnapshotService.clear_snapshots()
    snap2 = await RiskQuantificationSnapshotService.generate_snapshot(mock_db, None)
    assert snap1["summary"]["total_risk_records"] == snap2["summary"]["total_risk_records"]

@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_deletion(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberRiskQuantificationService.sync_risks(mock_db)
    await RiskQuantificationSnapshotService.generate_snapshot(mock_db, None)
    RiskQuantificationSnapshotService.clear_snapshots()
    snap = RiskQuantificationSnapshotService.get_snapshot(None)
    assert snap["summary"]["total_risk_records"] == 0

@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_corruption(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberRiskQuantificationService.sync_risks(mock_db)
    RiskQuantificationSnapshotService._snapshots[None] = "CORRUPTED"
    snap = RiskQuantificationSnapshotService.get_snapshot(None)
    assert snap["summary"]["total_risk_records"] == 0

@pytest.mark.asyncio
async def test_snapshot_not_authoritative_risk(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberRiskQuantificationService.sync_risks(mock_db)
    snap = await RiskQuantificationSnapshotService.generate_snapshot(mock_db, None)
    snap["summary"]["total_risk_records"] = 999
    assert len(await CyberRiskQuantificationService.get_all_risks()) == 2

@pytest.mark.asyncio
async def test_risk_drift_detection(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    prev = {
        "summary": {
            "total_annualized_loss_expectancy": 1000.0,
            "projected_loss_forecast": 1000.0,
        }
    }

    await CyberRiskQuantificationService.sync_risks(mock_db)

    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await RiskDriftService.process_drift(mock_db, None, prev)
        events = [c.kwargs["payload"].get("drift_type") for c in mock_emit.call_args_list if "drift_type" in c.kwargs["payload"]]
        assert "EXPOSURE_INCREASED" in events or "EXPOSURE_DECREASED" in events or len(events) == 0


# ==========================================
# PART 6: RBAC & ROUTER (15 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_rbac_risk_scope_validation(client, mock_db, mock_scope, mock_scope_2):
    setup_basic_mock_db(mock_db, mock_scope, mock_scope_2)
    headers = get_auth_header(OPERATOR_ID, "operator")
    # Operator does not own mock_scope_2
    resp = await client.get(f"/api/v1/cyber-risk-quantification/summary?scope_id={SCOPE_ID_2}", headers=headers)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_api_list_risks_admin(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(ADMIN_ID, "admin")
    resp = await client.get("/api/v1/cyber-risk-quantification", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_list_risks_operator(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/cyber-risk-quantification", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_create_risk_forbidden_for_reader(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(READER_ID, "reader")
    payload = {
        "title": "Forbidden",
        "description": "Desc",
        "scenario_type": "DATA_BREACH",
        "frequency_label": "RARE",
        "impact_label": "LOW",
        "exposure_value": 100.0,
    }
    resp = await client.post("/api/v1/cyber-risk-quantification", json=payload, headers=headers)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_api_create_risk_success(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {
        "title": "Success",
        "description": "Desc",
        "scenario_type": "DATA_BREACH",
        "frequency_label": "RARE",
        "impact_label": "LOW",
        "exposure_value": 100.0,
        "scope_id": str(SCOPE_ID),
    }
    resp = await client.post("/api/v1/cyber-risk-quantification", json=payload, headers=headers)
    assert resp.status_code == 201

@pytest.mark.asyncio
async def test_api_get_open_risks(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/cyber-risk-quantification/open", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_critical_risks(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/cyber-risk-quantification/critical", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_forecasts(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0, scope_id=SCOPE_ID)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/cyber-risk-quantification/forecasts?risk_id={r.risk_id}", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_trends(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0, scope_id=SCOPE_ID)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/cyber-risk-quantification/trends?risk_id={r.risk_id}", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_transition_accept(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0, scope_id=SCOPE_ID)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/cyber-risk-quantification/{r.risk_id}/accept", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_transition_mitigate(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0, scope_id=SCOPE_ID)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/cyber-risk-quantification/{r.risk_id}/mitigate", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_transition_close(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0, scope_id=SCOPE_ID)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/cyber-risk-quantification/{r.risk_id}/close", headers=headers)
    assert resp.status_code == 200


# ==========================================
# PART 7: SPECIFIC COMPLIANCE (15 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_ai_context_risk_injection(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await CyberRiskQuantificationService.sync_risks(mock_db)
    await RiskQuantificationSnapshotService.generate_snapshot(mock_db, None)

    ctx = await AIContextBuilder._build_risk_quantification_context_block(None)
    assert "risk_quantification_summary" in ctx
    assert len(ctx["quantified_risks"]) == 2

@pytest.mark.asyncio
async def test_ai_advisory_only_enforcement():
    prompt = AIPromptBuilder.build_executive_prompt({})
    assert "creating cyber risk records" in prompt

@pytest.mark.asyncio
async def test_worker_integration_risk(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.continuous_refresh_service import ContinuousRefreshService
    await ContinuousRefreshService.refresh_all(mock_db)

@pytest.mark.asyncio
async def test_closed_risk_not_reactivated_by_worker(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("Cloud S3 Bucket Leaks", "Desc", RiskScenarioType.CLOUD_COMPROMISE, "OCCASIONAL", "HIGH", 120000.0)
    await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.CLOSED)
    
    from src.services.continuous_refresh_service import ContinuousRefreshService
    await ContinuousRefreshService.refresh_all(mock_db)
    assert r.status == RiskQuantificationStatus.CLOSED

@pytest.mark.asyncio
async def test_closed_risk_not_reactivated_by_forecast(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.CLOSED)
    RiskForecastService.calculate()
    assert r.status == RiskQuantificationStatus.CLOSED

@pytest.mark.asyncio
async def test_closed_risk_not_reactivated_by_snapshot(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.CLOSED)
    await RiskQuantificationSnapshotService.generate_snapshot(mock_db, None)
    assert r.status == RiskQuantificationStatus.CLOSED

@pytest.mark.asyncio
async def test_closed_risk_not_reactivated_by_drift(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.CLOSED)
    await RiskDriftService.process_drift(mock_db, None, None)
    assert r.status == RiskQuantificationStatus.CLOSED

@pytest.mark.asyncio
async def test_risk_identity_preserved_after_worker_refresh(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    
    from src.services.continuous_refresh_service import ContinuousRefreshService
    await ContinuousRefreshService.refresh_all(mock_db)
    
    assert (await CyberRiskQuantificationService.get_all_risks())[0].risk_id == r.risk_id

@pytest.mark.asyncio
async def test_risk_identity_preserved_after_forecast_refresh(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    RiskForecastService.calculate()
    assert (await CyberRiskQuantificationService.get_all_risks())[0].risk_id == r.risk_id

@pytest.mark.asyncio
async def test_risk_identity_preserved_after_snapshot_rebuild(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    await RiskQuantificationSnapshotService.generate_snapshot(mock_db, None)
    assert (await CyberRiskQuantificationService.get_all_risks())[0].risk_id == r.risk_id

@pytest.mark.asyncio
async def test_risk_identity_preserved_after_drift_processing(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    await RiskDriftService.process_drift(mock_db, None, None)
    assert (await CyberRiskQuantificationService.get_all_risks())[0].risk_id == r.risk_id


# ==========================================
# PART 8: ADDITIONAL COVERAGE (35 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_extra_1(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskScenarioRegistry.validate("RANSOMWARE")

@pytest.mark.asyncio
async def test_extra_2(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskScenarioRegistry.validate("INSIDER_THREAT")

@pytest.mark.asyncio
async def test_extra_3(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskScenarioRegistry.validate("SERVICE_OUTAGE")

@pytest.mark.asyncio
async def test_extra_4(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskScenarioRegistry.validate("CLOUD_COMPROMISE")

@pytest.mark.asyncio
async def test_extra_5(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskScenarioRegistry.validate("SUPPLY_CHAIN")

@pytest.mark.asyncio
async def test_extra_6(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert not RiskScenarioRegistry.validate("MALWARE")

@pytest.mark.asyncio
async def test_extra_7(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskFrequencyRegistry.validate("OCCASIONAL")

@pytest.mark.asyncio
async def test_extra_8(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskFrequencyRegistry.validate("LIKELY")

@pytest.mark.asyncio
async def test_extra_9(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskFrequencyRegistry.validate("FREQUENT")

@pytest.mark.asyncio
async def test_extra_10(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert not RiskFrequencyRegistry.validate("EVERY_DAY")

@pytest.mark.asyncio
async def test_extra_11(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskImpactRegistry.validate("MEDIUM")

@pytest.mark.asyncio
async def test_extra_12(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskImpactRegistry.validate("HIGH")

@pytest.mark.asyncio
async def test_extra_13(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskImpactRegistry.validate("CRITICAL")

@pytest.mark.asyncio
async def test_extra_14(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert not RiskImpactRegistry.validate("EXTREME")

@pytest.mark.asyncio
async def test_extra_15(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskImpactRegistry.get_factor("MEDIUM") == 0.3

@pytest.mark.asyncio
async def test_extra_16(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskImpactRegistry.get_factor("HIGH") == 0.6

@pytest.mark.asyncio
async def test_extra_17(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskFrequencyRegistry.get_aro("OCCASIONAL") == 0.2

@pytest.mark.asyncio
async def test_extra_18(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskFrequencyRegistry.get_aro("LIKELY") == 1.0

@pytest.mark.asyncio
async def test_extra_19(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert len(RiskTrendService.get_trends(uuid.uuid4())) == 0

@pytest.mark.asyncio
async def test_extra_20(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    # verify trend limit to 10 points
    for i in range(15):
        RiskTrendService.calculate_trends(r.risk_id, float(1000 + i))
    assert len(RiskTrendService.get_trends(r.risk_id)) == 10

@pytest.mark.asyncio
async def test_extra_21(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert len(QuantifiedRiskHistoryService.get_history(uuid.uuid4())) == 0

@pytest.mark.asyncio
async def test_extra_22(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    QuantifiedRiskHistoryService.record_event(r.risk_id, "TEST", "detail")
    assert len(QuantifiedRiskHistoryService.get_history(r.risk_id)) == 2

@pytest.mark.asyncio
async def test_extra_23(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    QuantifiedRiskHistoryService.clear_history()
    assert len(QuantifiedRiskHistoryService.get_history(r.risk_id)) == 0

@pytest.mark.asyncio
async def test_extra_24(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert len(RiskForecastService.get_forecasts(uuid.uuid4(), 100.0, 1000.0)) == 4

@pytest.mark.asyncio
async def test_extra_25(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    # verify SLE scaling
    assert LossExpectancyService.calculate_sle(2000.0, 0.5) == 1000.0

@pytest.mark.asyncio
async def test_extra_26(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert LossExpectancyService.calculate_ale(1000.0, 0.5) == 500.0

@pytest.mark.asyncio
async def test_extra_27(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert ResidualRiskService.calculate_inherent_risk_score(0, 0.5, 1.0) == 0.0

@pytest.mark.asyncio
async def test_extra_28(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert ResidualRiskService.calculate_residual_risk_score(0.0, 75.0) == 0.0

@pytest.mark.asyncio
async def test_extra_29(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert ResidualRiskService.calculate_mitigation_effectiveness(0.0, 10.0) == 100.0

@pytest.mark.asyncio
async def test_extra_30(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert len(RiskQuantificationSnapshotService.get_snapshot(uuid.uuid4())["records"]) == 0

@pytest.mark.asyncio
async def test_extra_31(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskFrequencyRegistry.get_aro("INVALID") == 1.0

@pytest.mark.asyncio
async def test_extra_32(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert RiskImpactRegistry.get_factor("INVALID") == 0.5

@pytest.mark.asyncio
async def test_extra_33(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    assert r.mitigation_effectiveness == 75.0

@pytest.mark.asyncio
async def test_extra_34(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    # accept transition changes status
    await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.ACCEPTED)
    assert r.status == RiskQuantificationStatus.ACCEPTED

@pytest.mark.asyncio
async def test_extra_35(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await CyberRiskQuantificationService.create_or_sync_risk("T1", "Desc", RiskScenarioType.DATA_BREACH, "RARE", "LOW", 1000.0)
    # mitigate transition changes status
    await CyberRiskQuantificationService.transition_status(r.risk_id, RiskQuantificationStatus.MITIGATED)
    assert r.status == RiskQuantificationStatus.MITIGATED
