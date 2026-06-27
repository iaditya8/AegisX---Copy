import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from src.core.security import create_access_token
from src.domain.entities.workflow import WorkflowCreate
from src.infrastructure.celery.worker import celery_app
from src.infrastructure.database.models import (
    ScanRun,
    Scope,
    User,
    Workflow,
    WorkflowEvent,
)
from src.services.workflow_service import (
    cancel_scan_run,
    create_workflow,
    start_workflow,
)

# Standard User IDs
ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_A_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER_B_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")

# Scope IDs
SCOPE_A_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
SCOPE_B_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")

# Workflow IDs
WF_A_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
WF_B_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")

# Configure Celery globally for eager synchronous task execution in tests
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True


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
def mock_user_a() -> User:
    user = User()
    user.id = USER_A_ID
    user.username = "user_a"
    user.role = "operator"
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_user_b() -> User:
    user = User()
    user.id = USER_B_ID
    user.username = "user_b"
    user.role = "operator"
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_scope_a() -> Scope:
    s = Scope()
    s.id = SCOPE_A_ID
    s.owner_id = USER_A_ID
    s.name = "Scope A"
    s.type = "domain"
    s.definition = {"domains": ["a.com"]}
    s.created_at = datetime.now(timezone.utc)
    return s


@pytest.fixture
def mock_scope_b() -> Scope:
    s = Scope()
    s.id = SCOPE_B_ID
    s.owner_id = USER_B_ID
    s.name = "Scope B"
    s.type = "domain"
    s.definition = {"domains": ["b.com"]}
    s.created_at = datetime.now(timezone.utc)
    return s


@pytest.fixture
def mock_workflow_a() -> Workflow:
    w = Workflow()
    w.id = WF_A_ID
    w.owner_id = USER_A_ID
    w.name = "Workflow A"
    w.definition = {
        "steps": [
            {"type": "discovery", "config": {}},
            {"type": "port-scan", "config": {}},
        ]
    }
    w.state = "draft"
    w.created_at = datetime.now(timezone.utc)
    w.updated_at = datetime.now(timezone.utc)
    return w


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


# --- API Endpoint CRUD & RBAC Tests ---


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.workflows.list_workflows")
async def test_list_workflows_as_operator(
    mock_list_wf: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_user_a: User,
    mock_workflow_a: Workflow,
) -> None:
    mock_get_user.return_value = mock_user_a
    mock_list_wf.return_value = ([mock_workflow_a], 1)

    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.get("/api/v1/workflows", headers=headers)

    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert len(res["data"]) == 1
    assert res["data"][0]["name"] == "Workflow A"
    assert res["data"][0]["state"] == "draft"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.workflows.create_workflow")
async def test_create_workflow_as_operator(
    mock_create_wf: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_user_a: User,
    mock_workflow_a: Workflow,
) -> None:
    mock_get_user.return_value = mock_user_a
    mock_create_wf.return_value = mock_workflow_a

    payload = {"name": "New Workflow", "definition": {"steps": [{"type": "discovery"}]}}
    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.post("/api/v1/workflows", json=payload, headers=headers)

    assert response.status_code == 201
    assert "Location" in response.headers
    assert response.json()["success"] is True
    assert response.json()["data"]["state"] == "draft"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.workflows.get_workflow_by_id")
@patch("src.api.v1.routers.workflows.update_workflow")
async def test_update_workflow_state_active(
    mock_update_wf: MagicMock,
    mock_get_wf: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_user_a: User,
    mock_workflow_a: Workflow,
) -> None:
    mock_get_user.return_value = mock_user_a
    mock_get_wf.return_value = mock_workflow_a

    updated = Workflow()
    updated.id = mock_workflow_a.id
    updated.name = mock_workflow_a.name
    updated.definition = mock_workflow_a.definition
    updated.state = "active"
    updated.created_at = mock_workflow_a.created_at
    updated.updated_at = datetime.now(timezone.utc)
    mock_update_wf.return_value = updated

    payload = {"state": "active"}
    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.put(
        f"/api/v1/workflows/{WF_A_ID}", json=payload, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["state"] == "active"


# --- Workflow Start Ownership Validation Checks ---


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.workflows.get_workflow_by_id")
@patch("src.api.v1.routers.workflows.get_scope_by_id")
@patch("src.api.v1.routers.workflows.start_workflow")
async def test_start_workflow_authorized_success(
    mock_start_wf: MagicMock,
    mock_get_scope: MagicMock,
    mock_get_wf: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_user_a: User,
    mock_scope_a: Scope,
    mock_workflow_a: Workflow,
) -> None:
    """Operator starts a workflow they own with a scope they own."""
    mock_get_user.return_value = mock_user_a
    mock_get_wf.return_value = mock_workflow_a
    mock_get_scope.return_value = mock_scope_a

    run = ScanRun()
    run.id = uuid.uuid4()
    mock_start_wf.return_value = run

    payload = {"scope_id": str(SCOPE_A_ID)}
    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.post(
        f"/api/v1/workflows/{WF_A_ID}/start", json=payload, headers=headers
    )

    assert response.status_code == 202
    res = response.json()
    assert res["success"] is True
    assert res["data"]["run_id"] == str(run.id)
    assert res["data"]["status"] == "accepted"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.workflows.get_workflow_by_id")
@patch("src.api.v1.routers.workflows.get_scope_by_id")
async def test_start_workflow_unauthorized_scope(
    mock_get_scope: MagicMock,
    mock_get_wf: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_user_a: User,
    mock_scope_b: Scope,  # Owned by User B
    mock_workflow_a: Workflow,  # Owned by User A
) -> None:
    """Cross-resource check: User A tries to start workflow A using User B's scope."""
    mock_get_user.return_value = mock_user_a
    mock_get_wf.return_value = mock_workflow_a
    mock_get_scope.return_value = mock_scope_b

    payload = {"scope_id": str(SCOPE_B_ID)}
    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.post(
        f"/api/v1/workflows/{WF_A_ID}/start", json=payload, headers=headers
    )

    # Ownership check failed on the scope, must return 403
    assert response.status_code == 403


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.workflows.get_workflow_by_id")
async def test_start_workflow_unauthorized_workflow(
    mock_get_wf: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_user_b: User,  # User B
    mock_workflow_a: Workflow,  # Owned by User A
) -> None:
    """Ownership check: User B tries to start workflow A they do not own."""
    mock_get_user.return_value = mock_user_b
    mock_get_wf.return_value = mock_workflow_a

    payload = {"scope_id": str(SCOPE_B_ID)}
    headers = get_auth_header(USER_B_ID, "operator")
    response = await client.post(
        f"/api/v1/workflows/{WF_A_ID}/start", json=payload, headers=headers
    )

    # Ownership check failed on the workflow, must return 403
    assert response.status_code == 403


# --- ScanRun Details & Cancellation Tests ---


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.scan_runs.get_scan_run_by_id")
@patch("src.api.v1.routers.scan_runs.get_workflow_by_id")
async def test_get_scan_run_details(
    mock_get_wf: MagicMock,
    mock_get_run: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_user_a: User,
    mock_workflow_a: Workflow,
) -> None:
    mock_get_user.return_value = mock_user_a
    mock_get_wf.return_value = mock_workflow_a

    run = ScanRun()
    run.id = uuid.uuid4()
    run.workflow_id = WF_A_ID
    run.scope_id = SCOPE_A_ID
    run.type = "discovery"
    run.status = "running"
    run.created_at = datetime.now(timezone.utc)
    mock_get_run.return_value = run

    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.get(f"/api/v1/scan_runs/{run.id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "running"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.scan_runs.get_scan_run_by_id")
@patch("src.api.v1.routers.scan_runs.get_workflow_by_id")
@patch("src.api.v1.routers.scan_runs.cancel_scan_run")
async def test_cancel_scan_run_route(
    mock_cancel: MagicMock,
    mock_get_wf: MagicMock,
    mock_get_run: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_user_a: User,
    mock_workflow_a: Workflow,
) -> None:
    mock_get_user.return_value = mock_user_a
    mock_get_wf.return_value = mock_workflow_a

    run = ScanRun()
    run.id = uuid.uuid4()
    run.workflow_id = WF_A_ID
    run.status = "running"
    mock_get_run.return_value = run
    mock_cancel.return_value = True

    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.post(f"/api/v1/scan_runs/{run.id}/cancel", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"] is True


# --- Service Layer & Celery State Machine Execution Tests ---


@pytest.mark.asyncio
async def test_create_workflow_service(mock_db) -> None:
    wf_in = WorkflowCreate(
        name="Service Workflow", definition={"steps": [{"type": "discovery"}]}
    )
    res = await create_workflow(mock_db, wf_in, owner_id=USER_A_ID)

    assert res.name == "Service Workflow"
    assert res.state == "draft"  # Lifecycle state starts in 'draft'
    assert mock_db.commit.call_count == 1


@pytest.mark.asyncio
@patch("src.services.workflow_service.execute_workflow_task.delay")
async def test_start_workflow_service(mock_celery_delay, mock_db) -> None:
    workflow = Workflow()
    workflow.id = WF_A_ID
    workflow.name = "Work"
    workflow.definition = {"steps": [{"type": "port-scan"}]}

    # Mock get_workflow_by_id inside start_workflow
    with patch(
        "src.services.workflow_service.get_workflow_by_id",
        return_value=workflow,
    ):
        run = await start_workflow(mock_db, WF_A_ID, SCOPE_A_ID, actor_id=USER_A_ID)

        assert run.status == "pending"
        assert run.type == "port-scan"
        assert mock_db.commit.call_count == 1
        # Check Celery task delay was triggered
        mock_celery_delay.assert_called_once_with(
            str(WF_A_ID), str(run.id), str(SCOPE_A_ID)
        )


@pytest.mark.asyncio
async def test_celery_execution_state_transitions_and_events(mock_db) -> None:
    """Test full execution of Celery worker task under eager configuration."""
    workflow = Workflow()
    workflow.id = WF_A_ID
    workflow.name = "Eager Workflow"
    workflow.definition = {
        "steps": [
            {"type": "discovery", "config": {}},
            {"type": "port-scan", "config": {}},
        ]
    }
    workflow.state = "active"

    run = ScanRun()
    run.id = uuid.uuid4()
    run.workflow_id = WF_A_ID
    run.scope_id = SCOPE_A_ID
    run.status = "pending"

    mock_scope = Scope()
    mock_scope.id = SCOPE_A_ID
    mock_scope.owner_id = None
    mock_scope.deleted_at = None

    # Mock DB operations inside the Celery task
    mock_db.get.side_effect = [workflow, run, mock_scope]

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db

    with patch(
        "src.infrastructure.celery.worker.AsyncSessionLocal",
        mock_session_factory,
    ):
        # Execute the Celery task synchronously
        from src.infrastructure.celery.worker import _execute_workflow_async

        await _execute_workflow_async(WF_A_ID, run.id, SCOPE_A_ID)

    # ScanRun should transition to completed
    assert run.status == "completed"
    assert run.end_ts is not None

    # Assert db.add was called for all step & lifecycle events
    # Expected events: workflow.started, step.started (step 0), step.completed (step 0),
    # step.started (step 1), step.completed (step 1), workflow.completed
    # Total event adds: at least 6 (can be more due to reporting/alerting/drift/TI checks)
    assert mock_db.add.call_count >= 6

    # For every event created, make sure it has correlation_id mapping to run.id
    for call_args in mock_db.add.call_args_list:
        added_obj = call_args[0][0]
        if isinstance(added_obj, WorkflowEvent) and (
            added_obj.event_type.startswith("workflow.") or added_obj.event_type.startswith("step.")
        ):
            assert added_obj.correlation_id == run.id


@pytest.mark.asyncio
@patch("src.services.workflow_service.get_scan_run_by_id")
async def test_cancel_scan_run_service(mock_get_run, mock_db) -> None:
    run = ScanRun()
    run.id = uuid.uuid4()
    run.status = "running"
    mock_get_run.return_value = run

    success = await cancel_scan_run(mock_db, run.id)
    assert success is True
    assert run.status == "cancelled"
    assert mock_db.commit.call_count == 1
