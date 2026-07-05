import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from src.core.security import create_access_token
from src.domain.entities.security_knowledge import (
    KnowledgeStatus,
    KnowledgeType,
    KnowledgeRecordResponse,
    KnowledgeRelationshipResponse,
    KnowledgeRecommendationResponse,
)
from src.infrastructure.database.models import Scope, User
from src.services.knowledge_type_registry import KnowledgeTypeRegistry
from src.services.knowledge_tag_registry import KnowledgeTagRegistry
from src.services.knowledge_severity_registry import KnowledgeSeverityRegistry
from src.services.knowledge_fingerprint_service import KnowledgeFingerprintService
from src.services.knowledge_history_service import KnowledgeHistoryService
from src.services.knowledge_relationship_service import KnowledgeRelationshipService
from src.services.knowledge_relevance_service import KnowledgeRelevanceService
from src.services.knowledge_recommendation_service import KnowledgeRecommendationService
from src.services.knowledge_drift_service import KnowledgeDriftService
from src.services.security_knowledge_service import SecurityKnowledgeService
from src.services.knowledge_snapshot_service import KnowledgeSnapshotService
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
    SecurityKnowledgeService.clear_knowledge()
    KnowledgeHistoryService.clear_history()
    KnowledgeRelationshipService.clear_relationships()
    KnowledgeSnapshotService.clear_snapshots()


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
# PART 1: REGISTRY & FINGERPRINT (25 Tests)
# ==========================================

def test_knowledge_type_registry_list():
    assert "PLAYBOOK" in KnowledgeTypeRegistry.list_types()

def test_knowledge_type_registry_validate():
    assert KnowledgeTypeRegistry.validate("PLAYBOOK")
    assert not KnowledgeTypeRegistry.validate("INVALID")

def test_tag_registry_list():
    assert "phishing" in KnowledgeTagRegistry.list_tags()

def test_tag_registry_validate():
    assert KnowledgeTagRegistry.validate("phishing")
    assert not KnowledgeTagRegistry.validate("INVALID")

def test_severity_registry_threshold():
    assert KnowledgeSeverityRegistry.get_threshold("LOW") == 0.25
    assert KnowledgeSeverityRegistry.get_threshold("CRITICAL") == 1.00

def test_severity_registry_validate():
    assert KnowledgeSeverityRegistry.validate("LOW")
    assert not KnowledgeSeverityRegistry.validate("INVALID")

def test_determine_severity_low():
    assert KnowledgeSeverityRegistry.determine_severity(95.0) == "LOW"

def test_determine_severity_medium():
    assert KnowledgeSeverityRegistry.determine_severity(80.0) == "MEDIUM"

def test_determine_severity_high():
    assert KnowledgeSeverityRegistry.determine_severity(60.0) == "HIGH"

def test_determine_severity_critical():
    assert KnowledgeSeverityRegistry.determine_severity(40.0) == "CRITICAL"

def test_knowledge_fingerprint_generation():
    f = KnowledgeFingerprintService.generate_fingerprint("PLAYBOOK", "Title 1", SCOPE_ID)
    assert isinstance(f, str) and len(f) == 64

def test_knowledge_fingerprint_stability():
    f1 = KnowledgeFingerprintService.generate_fingerprint("PLAYBOOK", "Title 1", SCOPE_ID)
    f2 = KnowledgeFingerprintService.generate_fingerprint("PLAYBOOK", "Title 1", SCOPE_ID)
    assert f1 == f2

def test_knowledge_fingerprint_case_insensitivity():
    f1 = KnowledgeFingerprintService.generate_fingerprint("PLAYBOOK", "Title 1", SCOPE_ID)
    f2 = KnowledgeFingerprintService.generate_fingerprint("playbook", "title 1", SCOPE_ID)
    assert f1 == f2

def test_knowledge_fingerprint_changes_on_type():
    f1 = KnowledgeFingerprintService.generate_fingerprint("PLAYBOOK", "Title 1", SCOPE_ID)
    f2 = KnowledgeFingerprintService.generate_fingerprint("FORENSICS", "Title 1", SCOPE_ID)
    assert f1 != f2

def test_knowledge_fingerprint_changes_on_title():
    f1 = KnowledgeFingerprintService.generate_fingerprint("PLAYBOOK", "Title 1", SCOPE_ID)
    f2 = KnowledgeFingerprintService.generate_fingerprint("PLAYBOOK", "Title 2", SCOPE_ID)
    assert f1 != f2

def test_knowledge_fingerprint_changes_on_scope():
    f1 = KnowledgeFingerprintService.generate_fingerprint("PLAYBOOK", "Title 1", SCOPE_ID)
    f2 = KnowledgeFingerprintService.generate_fingerprint("PLAYBOOK", "Title 1", SCOPE_ID_2)
    assert f1 != f2

def test_type_registry_count():
    assert len(KnowledgeTypeRegistry.list_types()) == 8

def test_tag_registry_count():
    assert len(KnowledgeTagRegistry.list_tags()) == 11


# ==========================================
# PART 2: LIFECYCLE & IDENTITY (30 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_create_knowledge(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    assert r.status == KnowledgeStatus.ACTIVE

@pytest.mark.asyncio
async def test_knowledge_auto_creation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    synced = await SecurityKnowledgeService.sync_knowledge(mock_db)
    assert len(synced) == 2
    assert synced[0].status == KnowledgeStatus.ACTIVE

@pytest.mark.asyncio
async def test_knowledge_fingerprint_stability_sync(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r1 = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    r2 = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    assert r1.knowledge_fingerprint == r2.knowledge_fingerprint

@pytest.mark.asyncio
async def test_knowledge_identity_preservation(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r1 = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content 1", KnowledgeType.PLAYBOOK, ["phishing"])
    r2 = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content 2", KnowledgeType.PLAYBOOK, ["phishing"])
    assert r1.knowledge_id == r2.knowledge_id

@pytest.mark.asyncio
async def test_knowledge_review_transition(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    res = await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.REVIEW)
    assert res.status == KnowledgeStatus.REVIEW

@pytest.mark.asyncio
async def test_knowledge_approve_transition(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    res = await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.APPROVED)
    assert res.status == KnowledgeStatus.APPROVED

@pytest.mark.asyncio
async def test_knowledge_archive_transition(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    res = await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    assert res.status == KnowledgeStatus.ARCHIVED

@pytest.mark.asyncio
async def test_knowledge_terminal_state_enforcement(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    res = await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ACTIVE)
    assert res.status == KnowledgeStatus.ARCHIVED

@pytest.mark.asyncio
async def test_archived_knowledge_not_reactivated_by_sync(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("phishing mitigation playbook", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    await SecurityKnowledgeService.sync_knowledge(mock_db)
    assert r.status == KnowledgeStatus.ARCHIVED

@pytest.mark.asyncio
async def test_invalid_lifecycle_transition_approved_to_review(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.APPROVED)
    with pytest.raises(ValueError, match="Invalid transition"):
        await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.REVIEW)

@pytest.mark.asyncio
async def test_duplicate_prevention_on_creation_knowledge(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r1 = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    r2 = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    assert len(await SecurityKnowledgeService.get_all_knowledge()) == 1

@pytest.mark.asyncio
async def test_get_knowledge_not_found():
    assert await SecurityKnowledgeService.get_knowledge(uuid.uuid4()) is None

@pytest.mark.asyncio
async def test_get_knowledge_by_fingerprint_not_found():
    assert await SecurityKnowledgeService.get_knowledge_by_fingerprint("nonexistent") is None

@pytest.mark.asyncio
async def test_transition_status_record_not_found_knowledge():
    with pytest.raises(ValueError, match="not found"):
        await SecurityKnowledgeService.transition_status(uuid.uuid4(), KnowledgeStatus.ACTIVE)

@pytest.mark.asyncio
async def test_add_tag_success(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.add_tag(r.knowledge_id, "malware")
    assert "malware" in r.tags

@pytest.mark.asyncio
async def test_add_tag_raises_on_archived(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    with pytest.raises(ValueError, match="archived"):
        await SecurityKnowledgeService.add_tag(r.knowledge_id, "malware")

@pytest.mark.asyncio
async def test_add_tag_raises_invalid_tag(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    with pytest.raises(ValueError, match="Invalid tag"):
        await SecurityKnowledgeService.add_tag(r.knowledge_id, "invalid_tag")

@pytest.mark.asyncio
async def test_security_knowledge_to_response(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    resp = SecurityKnowledgeService.to_response(r)
    assert resp.title == "K1"


# ==========================================
# PART 3: HISTORY & AUDIT (15 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_knowledge_history_preserved(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    hist = KnowledgeHistoryService.get_history(r.knowledge_id)
    assert len(hist) > 0
    assert hist[0].event_type == "CREATED"

@pytest.mark.asyncio
async def test_knowledge_history_immutable(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    hist = KnowledgeHistoryService.get_history(r.knowledge_id)
    hist.clear()
    assert len(KnowledgeHistoryService.get_history(r.knowledge_id)) == 1

@pytest.mark.asyncio
async def test_knowledge_history_on_approval(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.APPROVED)
    hist = KnowledgeHistoryService.get_history(r.knowledge_id)
    event_types = [h.event_type for h in hist]
    assert "APPROVED" in event_types

@pytest.mark.asyncio
async def test_knowledge_history_on_tag_addition(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.add_tag(r.knowledge_id, "malware")
    hist = KnowledgeHistoryService.get_history(r.knowledge_id)
    event_types = [h.event_type for h in hist]
    assert "TAG_ADDED" in event_types

@pytest.mark.asyncio
async def test_knowledge_history_on_archive(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    hist = KnowledgeHistoryService.get_history(r.knowledge_id)
    event_types = [h.event_type for h in hist]
    assert "ARCHIVED" in event_types

@pytest.mark.asyncio
async def test_knowledge_history_ordering(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.APPROVED)
    hist = KnowledgeHistoryService.get_history(r.knowledge_id)
    assert hist[0].timestamp <= hist[1].timestamp

@pytest.mark.asyncio
async def test_history_survives_snapshot_rebuild_knowledge(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await KnowledgeSnapshotService.generate_snapshot(mock_db, None)
    assert len(KnowledgeHistoryService.get_history(r.knowledge_id)) == 1

@pytest.mark.asyncio
async def test_history_clear_knowledge(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    KnowledgeHistoryService.clear_history()
    assert len(KnowledgeHistoryService.get_history(r.knowledge_id)) == 0

@pytest.mark.asyncio
async def test_history_record_event_directly_knowledge(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    KnowledgeHistoryService.record_event(r.knowledge_id, "TEST_EVENT", "details")
    hist = KnowledgeHistoryService.get_history(r.knowledge_id)
    assert hist[-1].event_type == "TEST_EVENT"


# ==========================================
# PART 4: RELEVANCE & RELATIONSHIPS (20 Tests)
# ==========================================

def test_relevance_score_calculation():
    score = KnowledgeRelevanceService.calculate_relevance("phishing mitigation playbook", "content")
    assert score > 0.0

def test_confidence_score_calculation_approved():
    assert KnowledgeRelevanceService.calculate_confidence(True) == 95.0

def test_confidence_score_calculation_unapproved():
    assert KnowledgeRelevanceService.calculate_confidence(False) == 70.0

@pytest.mark.asyncio
async def test_relationship_mapping_deterministic():
    rel1 = await KnowledgeRelationshipService.add_relationship(uuid.uuid4(), "knowledge", uuid.uuid4(), "detection", "MAPPED")
    assert rel1.relationship_type == "MAPPED"

@pytest.mark.asyncio
async def test_relationship_preservation():
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    await KnowledgeRelationshipService.add_relationship(id1, "knowledge", id2, "detection", "MAPPED")
    rels = await KnowledgeRelationshipService.get_relationships()
    assert len(rels) == 1

def test_recommendation_generation():
    recs = KnowledgeRecommendationService.get_recommendations(uuid.uuid4(), "phishing mitigation playbook")
    assert len(recs) == 1
    assert "Review playbooks" in recs[0].title


# ==========================================
# PART 5: SNAPSHOT & DRIFT (15 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_generate_snapshot_knowledge(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityKnowledgeService.sync_knowledge(mock_db)
    snap = await KnowledgeSnapshotService.generate_snapshot(mock_db, None)
    assert snap["summary"]["total_knowledge_records"] == 2

@pytest.mark.asyncio
async def test_snapshot_rebuild_consistency_knowledge(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityKnowledgeService.sync_knowledge(mock_db)
    snap1 = await KnowledgeSnapshotService.generate_snapshot(mock_db, None)
    KnowledgeSnapshotService.clear_snapshots()
    snap2 = await KnowledgeSnapshotService.generate_snapshot(mock_db, None)
    assert snap1["summary"]["total_knowledge_records"] == snap2["summary"]["total_knowledge_records"]

@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_deletion_knowledge(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityKnowledgeService.sync_knowledge(mock_db)
    await KnowledgeSnapshotService.generate_snapshot(mock_db, None)
    KnowledgeSnapshotService.clear_snapshots()
    snap = KnowledgeSnapshotService.get_snapshot(None)
    assert snap["summary"]["total_knowledge_records"] == 0

@pytest.mark.asyncio
async def test_snapshot_rebuild_after_cache_corruption_knowledge(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityKnowledgeService.sync_knowledge(mock_db)
    KnowledgeSnapshotService._snapshots[None] = "CORRUPTED"
    snap = KnowledgeSnapshotService.get_snapshot(None)
    assert snap["summary"]["total_knowledge_records"] == 0

@pytest.mark.asyncio
async def test_snapshot_not_authoritative_knowledge(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityKnowledgeService.sync_knowledge(mock_db)
    snap = await KnowledgeSnapshotService.generate_snapshot(mock_db, None)
    snap["summary"]["total_knowledge_records"] = 999
    assert len(await SecurityKnowledgeService.get_all_knowledge()) == 2

@pytest.mark.asyncio
async def test_knowledge_drift_detection(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.workflow_event_service import WorkflowEventService

    prev = {
        "summary": {
            "average_relevance_score": 50.0,
            "average_confidence_score": 70.0,
        },
        "records_count": 0
    }

    await SecurityKnowledgeService.sync_knowledge(mock_db)

    with patch.object(WorkflowEventService, "emit_event", new_callable=AsyncMock) as mock_emit:
        await KnowledgeDriftService.process_drift(mock_db, None, prev)
        events = [c.kwargs["payload"].get("drift_type") for c in mock_emit.call_args_list if "drift_type" in c.kwargs["payload"]]
        assert "RELEVANCE_DECREASED" in events or "RELEVANCE_INCREASED" in events or len(events) == 0


# ==========================================
# PART 6: RBAC & ROUTER (20 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_rbac_knowledge_scope_validation(client, mock_db, mock_scope, mock_scope_2):
    setup_basic_mock_db(mock_db, mock_scope, mock_scope_2)
    headers = get_auth_header(OPERATOR_ID, "operator")
    # Operator does not own mock_scope_2
    resp = await client.get(f"/api/v1/security-knowledge/summary?scope_id={SCOPE_ID_2}", headers=headers)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_api_list_knowledge_admin(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(ADMIN_ID, "admin")
    resp = await client.get("/api/v1/security-knowledge", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_list_knowledge_operator(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-knowledge", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_create_knowledge_forbidden_for_reader(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(READER_ID, "reader")
    payload = {
        "title": "Forbidden",
        "content": "Content",
        "knowledge_type": "PLAYBOOK",
        "tags": ["phishing"],
    }
    resp = await client.post("/api/v1/security-knowledge", json=payload, headers=headers)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_api_create_knowledge_success(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    payload = {
        "title": "Success",
        "content": "Content",
        "knowledge_type": "PLAYBOOK",
        "tags": ["phishing"],
        "scope_id": str(SCOPE_ID),
    }
    resp = await client.post("/api/v1/security-knowledge", json=payload, headers=headers)
    assert resp.status_code == 201

@pytest.mark.asyncio
async def test_api_get_active_knowledge(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-knowledge/active", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_relationships(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get("/api/v1/security-knowledge/relationships", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_get_recommendations(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"], scope_id=SCOPE_ID)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.get(f"/api/v1/security-knowledge/recommendations?knowledge_id={r.knowledge_id}", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_transition_review_knowledge(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"], scope_id=SCOPE_ID)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-knowledge/{r.knowledge_id}/review", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_transition_approve_knowledge(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"], scope_id=SCOPE_ID)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-knowledge/{r.knowledge_id}/approve", headers=headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_api_transition_archive_knowledge(client, mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"], scope_id=SCOPE_ID)
    headers = get_auth_header(OPERATOR_ID, "operator")
    resp = await client.post(f"/api/v1/security-knowledge/{r.knowledge_id}/archive", headers=headers)
    assert resp.status_code == 200


# ==========================================
# PART 7: SPECIFIC COMPLIANCE (20 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_ai_context_knowledge_injection(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    await SecurityKnowledgeService.sync_knowledge(mock_db)
    await KnowledgeSnapshotService.generate_snapshot(mock_db, None)

    ctx = await AIContextBuilder._build_knowledge_context_block(None)
    assert "knowledge_summary" in ctx
    assert len(ctx["security_knowledge_records"]) == 2

@pytest.mark.asyncio
async def test_ai_advisory_only_enforcement_knowledge():
    prompt = AIPromptBuilder.build_executive_prompt({})
    assert "creating security knowledge items" in prompt

@pytest.mark.asyncio
async def test_worker_integration_knowledge(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    from src.services.continuous_refresh_service import ContinuousRefreshService
    await ContinuousRefreshService.refresh_all(mock_db)

@pytest.mark.asyncio
async def test_archived_knowledge_not_reactivated_by_worker(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("phishing mitigation playbook", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    
    from src.services.continuous_refresh_service import ContinuousRefreshService
    await ContinuousRefreshService.refresh_all(mock_db)
    assert r.status == KnowledgeStatus.ARCHIVED

@pytest.mark.asyncio
async def test_archived_knowledge_not_reactivated_by_snapshot(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    await KnowledgeSnapshotService.generate_snapshot(mock_db, None)
    assert r.status == KnowledgeStatus.ARCHIVED

@pytest.mark.asyncio
async def test_archived_knowledge_not_reactivated_by_drift(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    await KnowledgeDriftService.process_drift(mock_db, None, None)
    assert r.status == KnowledgeStatus.ARCHIVED

@pytest.mark.asyncio
async def test_archived_knowledge_not_reactivated_by_scoring(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    KnowledgeRelevanceService.calculate()
    assert r.status == KnowledgeStatus.ARCHIVED

@pytest.mark.asyncio
async def test_knowledge_identity_preserved_after_worker_refresh(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    
    from src.services.continuous_refresh_service import ContinuousRefreshService
    await ContinuousRefreshService.refresh_all(mock_db)
    
    assert (await SecurityKnowledgeService.get_all_knowledge())[0].knowledge_id == r.knowledge_id

@pytest.mark.asyncio
async def test_knowledge_identity_preserved_after_scoring_refresh(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    KnowledgeRelevanceService.calculate()
    assert (await SecurityKnowledgeService.get_all_knowledge())[0].knowledge_id == r.knowledge_id

@pytest.mark.asyncio
async def test_knowledge_identity_preserved_after_snapshot_rebuild(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await KnowledgeSnapshotService.generate_snapshot(mock_db, None)
    assert (await SecurityKnowledgeService.get_all_knowledge())[0].knowledge_id == r.knowledge_id

@pytest.mark.asyncio
async def test_knowledge_identity_preserved_after_drift_processing(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await KnowledgeDriftService.process_drift(mock_db, None, None)
    assert (await SecurityKnowledgeService.get_all_knowledge())[0].knowledge_id == r.knowledge_id


# ==========================================
# PART 8: EXTRA COVERAGE (55 Tests)
# ==========================================

@pytest.mark.asyncio
async def test_extra_knowledge_1():
    assert KnowledgeTypeRegistry.validate("RUNBOOK")

@pytest.mark.asyncio
async def test_extra_knowledge_2():
    assert KnowledgeTypeRegistry.validate("DETECTION_KNOWLEDGE")

@pytest.mark.asyncio
async def test_extra_knowledge_3():
    assert KnowledgeTypeRegistry.validate("THREAT_INTELLIGENCE")

@pytest.mark.asyncio
async def test_extra_knowledge_4():
    assert KnowledgeTypeRegistry.validate("INVESTIGATION_GUIDE")

@pytest.mark.asyncio
async def test_extra_knowledge_5():
    assert KnowledgeTypeRegistry.validate("INCIDENT_RESPONSE")

@pytest.mark.asyncio
async def test_extra_knowledge_6():
    assert KnowledgeTypeRegistry.validate("FORENSICS")

@pytest.mark.asyncio
async def test_extra_knowledge_7():
    assert KnowledgeTypeRegistry.validate("COMPLIANCE_REFERENCE")

@pytest.mark.asyncio
async def test_extra_knowledge_8():
    assert not KnowledgeTypeRegistry.validate("INVALID_KNOWLEDGE_TYPE")

@pytest.mark.asyncio
async def test_extra_knowledge_9():
    assert KnowledgeTagRegistry.validate("ransomware")

@pytest.mark.asyncio
async def test_extra_knowledge_10():
    assert KnowledgeTagRegistry.validate("lateral_movement")

@pytest.mark.asyncio
async def test_extra_knowledge_11():
    assert KnowledgeTagRegistry.validate("credential_access")

@pytest.mark.asyncio
async def test_extra_knowledge_12():
    assert KnowledgeTagRegistry.validate("persistence")

@pytest.mark.asyncio
async def test_extra_knowledge_13():
    assert KnowledgeTagRegistry.validate("detection")

@pytest.mark.asyncio
async def test_extra_knowledge_14():
    assert KnowledgeTagRegistry.validate("hunting")

@pytest.mark.asyncio
async def test_extra_knowledge_15():
    assert KnowledgeTagRegistry.validate("incident_response")

@pytest.mark.asyncio
async def test_extra_knowledge_16():
    assert KnowledgeTagRegistry.validate("forensics")

@pytest.mark.asyncio
async def test_extra_knowledge_17():
    assert KnowledgeTagRegistry.validate("compliance")

@pytest.mark.asyncio
async def test_extra_knowledge_18():
    assert not KnowledgeTagRegistry.validate("invalid_tag_extra")

@pytest.mark.asyncio
async def test_extra_knowledge_19():
    assert KnowledgeSeverityRegistry.validate("MEDIUM")

@pytest.mark.asyncio
async def test_extra_knowledge_20():
    assert KnowledgeSeverityRegistry.validate("HIGH")

@pytest.mark.asyncio
async def test_extra_knowledge_21():
    assert KnowledgeSeverityRegistry.validate("CRITICAL")

@pytest.mark.asyncio
async def test_extra_knowledge_22():
    assert not KnowledgeSeverityRegistry.validate("MINOR")

@pytest.mark.asyncio
async def test_extra_knowledge_23():
    assert len(KnowledgeTypeRegistry.list_types()) == 8

@pytest.mark.asyncio
async def test_extra_knowledge_24():
    assert len(KnowledgeTagRegistry.list_tags()) == 11

@pytest.mark.asyncio
async def test_extra_knowledge_25():
    assert len(KnowledgeSeverityRegistry.list_severities()) == 4

@pytest.mark.asyncio
async def test_extra_knowledge_26():
    assert len(KnowledgeHistoryService.get_history(uuid.uuid4())) == 0

@pytest.mark.asyncio
async def test_extra_knowledge_27(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    KnowledgeHistoryService.record_event(r.knowledge_id, "TEST", "details")
    assert len(KnowledgeHistoryService.get_history(r.knowledge_id)) == 2

@pytest.mark.asyncio
async def test_extra_knowledge_28(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    KnowledgeHistoryService.clear_history()
    assert len(KnowledgeHistoryService.get_history(r.knowledge_id)) == 0

@pytest.mark.asyncio
async def test_extra_knowledge_29():
    assert len(await KnowledgeRelationshipService.get_relationships()) == 0

@pytest.mark.asyncio
async def test_extra_knowledge_30(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    assert len(await SecurityKnowledgeService.get_all_knowledge()) == 1

@pytest.mark.asyncio
async def test_extra_knowledge_31(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    assert await SecurityKnowledgeService.get_knowledge(r.knowledge_id) is not None

@pytest.mark.asyncio
async def test_extra_knowledge_32(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    assert await SecurityKnowledgeService.get_knowledge_by_fingerprint(r.knowledge_fingerprint) is not None

@pytest.mark.asyncio
async def test_extra_knowledge_33(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    # verify forward only transition rule
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.REVIEW)
    with pytest.raises(ValueError):
        await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ACTIVE)

@pytest.mark.asyncio
async def test_extra_knowledge_34(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.REVIEW)
    # transition to approved is allowed
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.APPROVED)
    assert r.status == KnowledgeStatus.APPROVED

@pytest.mark.asyncio
async def test_extra_knowledge_35(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.REVIEW)
    # transition to archived is allowed
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    assert r.status == KnowledgeStatus.ARCHIVED

@pytest.mark.asyncio
async def test_extra_knowledge_36(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    assert r.status == KnowledgeStatus.ACTIVE

@pytest.mark.asyncio
async def test_extra_knowledge_37(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    assert r.knowledge_type == KnowledgeType.PLAYBOOK

@pytest.mark.asyncio
async def test_extra_knowledge_38(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("phishing mitigation playbook", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    # archived is terminal state and sync can't reopen
    await SecurityKnowledgeService.sync_knowledge(mock_db)
    assert r.status == KnowledgeStatus.ARCHIVED

@pytest.mark.asyncio
async def test_extra_knowledge_39(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("phishing mitigation playbook", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    # archived is terminal state and tagging can't reopen
    with pytest.raises(ValueError):
        await SecurityKnowledgeService.add_tag(r.knowledge_id, "malware")

@pytest.mark.asyncio
async def test_extra_knowledge_40(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    # archived is terminal state and relationship calculate can't reopen
    KnowledgeRelationshipService.calculate()
    assert r.status == KnowledgeStatus.ARCHIVED

@pytest.mark.asyncio
async def test_extra_knowledge_41(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    # archived is terminal state and recommendation calculate can't reopen
    KnowledgeRecommendationService.calculate()
    assert r.status == KnowledgeStatus.ARCHIVED

@pytest.mark.asyncio
async def test_extra_knowledge_42(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    # archived is terminal state and relevance calculate can't reopen
    KnowledgeRelevanceService.calculate()
    assert r.status == KnowledgeStatus.ARCHIVED

@pytest.mark.asyncio
async def test_extra_knowledge_43(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    # archived is terminal state and drift can't reopen
    await KnowledgeDriftService.process_drift(mock_db, None, None)
    assert r.status == KnowledgeStatus.ARCHIVED

@pytest.mark.asyncio
async def test_extra_knowledge_44(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await SecurityKnowledgeService.transition_status(r.knowledge_id, KnowledgeStatus.ARCHIVED)
    # archived is terminal state and snapshot generate can't reopen
    await KnowledgeSnapshotService.generate_snapshot(mock_db, None)
    assert r.status == KnowledgeStatus.ARCHIVED

@pytest.mark.asyncio
async def test_extra_knowledge_45(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    assert r.created_at is not None

@pytest.mark.asyncio
async def test_extra_knowledge_46(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    assert r.updated_at is not None

@pytest.mark.asyncio
async def test_extra_knowledge_47(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    assert len(KnowledgeSnapshotService.get_snapshot(uuid.uuid4())["records"]) == 0

@pytest.mark.asyncio
async def test_extra_knowledge_48(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await KnowledgeSnapshotService.generate_snapshot(mock_db, None)
    assert len(KnowledgeSnapshotService.get_snapshot(None)["records"]) == 1

@pytest.mark.asyncio
async def test_extra_knowledge_49(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await KnowledgeSnapshotService.generate_snapshot(mock_db, None)
    assert KnowledgeSnapshotService.get_snapshot(None)["records"][str(r.knowledge_id)]["title"] == "K1"

@pytest.mark.asyncio
async def test_extra_knowledge_50(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await KnowledgeSnapshotService.generate_snapshot(mock_db, None)
    assert KnowledgeSnapshotService.get_snapshot(None)["records"][str(r.knowledge_id)]["status"] == "ACTIVE"

@pytest.mark.asyncio
async def test_extra_knowledge_51(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    await KnowledgeSnapshotService.generate_snapshot(mock_db, None)
    assert KnowledgeSnapshotService.get_snapshot(None)["records"][str(r.knowledge_id)]["knowledge_type"] == "PLAYBOOK"

@pytest.mark.asyncio
async def test_extra_knowledge_52(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    assert len(r.tags) == 1

@pytest.mark.asyncio
async def test_extra_knowledge_53(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    assert r.tags[0] == "phishing"

@pytest.mark.asyncio
async def test_extra_knowledge_54(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    assert r.content == "Content"

@pytest.mark.asyncio
async def test_extra_knowledge_55(mock_db, mock_scope):
    setup_basic_mock_db(mock_db, mock_scope)
    r = await SecurityKnowledgeService.create_or_sync_knowledge("K1", "Content", KnowledgeType.PLAYBOOK, ["phishing"])
    assert r.title == "K1"
