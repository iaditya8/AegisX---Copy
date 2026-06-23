import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from src.core.security import create_access_token
from src.domain.entities.plugin import PluginManifest
from src.infrastructure.database.models import (
    Plugin,
    ScanRun,
    Scope,
    User,
    Workflow,
    WorkflowEvent,
)
from src.plugins.host import PluginExecutionError, PluginHost, PluginValidationError
from src.plugins.mock_plugin import MockDiscoveryPlugin
from src.services.plugin_service import (
    approve_plugin_by_id,
)

ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_A_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
SCOPE_A_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
WF_A_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
PLUGIN_A_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


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
def mock_plugin_a() -> Plugin:
    p = Plugin()
    p.id = PLUGIN_A_ID
    p.name = "mock-discovery"
    p.version = "1.0.0"
    p.manifest = {
        "name": "mock-discovery",
        "version": "1.0.0",
        "entry_point": "src.plugins.mock_plugin:MockDiscoveryPlugin",
        "capabilities": ["discovery"],
        "permissions": ["network"],
        "timeout": 30,
    }
    p.state = "draft"
    p.installed_at = datetime.now(timezone.utc)
    return p


# --- 1. Plugin Registration & Manifest Validation Tests ---


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.plugins.register_plugin")
async def test_plugin_registration(
    mock_reg: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_admin: User,
    mock_plugin_a: Plugin,
) -> None:
    """Test standard plugin registration API. Newly registered starts in draft."""
    mock_get_user.return_value = mock_admin
    mock_reg.return_value = mock_plugin_a

    payload = {
        "name": "mock-discovery",
        "version": "1.0.0",
        "manifest": {
            "name": "mock-discovery",
            "version": "1.0.0",
            "entry_point": "src.plugins.mock_plugin:MockDiscoveryPlugin",
            "capabilities": ["discovery"],
            "permissions": ["network"],
            "timeout": 30,
        },
    }
    headers = get_auth_header(ADMIN_ID, "admin")
    response = await client.post("/api/v1/plugins", json=payload, headers=headers)

    assert response.status_code == 201
    assert "Location" in response.headers
    res = response.json()
    assert res["success"] is True
    assert res["data"]["state"] == "draft"


@pytest.mark.asyncio
async def test_manifest_validation_fields() -> None:
    """Test validation of required fields on the manifest schema."""
    invalid_manifest = {
        "name": "invalid-plugin",
        # missing version, entry_point, capabilities, timeout
    }
    with pytest.raises(Exception):
        PluginManifest(**invalid_manifest)


def test_semver_validation() -> None:
    """Test validation of SemVer version strings."""
    # Valid SemVer strings
    assert PluginManifest.validate_semver("1.0.0") == "1.0.0"
    assert PluginManifest.validate_semver("2.5.12") == "2.5.12"
    assert PluginManifest.validate_semver("0.1.0-beta.1") == "0.1.0-beta.1"

    # Invalid SemVer strings should raise ValueError
    with pytest.raises(ValueError):
        PluginManifest.validate_semver("1")
    with pytest.raises(ValueError):
        PluginManifest.validate_semver("1.0")
    with pytest.raises(ValueError):
        PluginManifest.validate_semver("1.a.0")
    with pytest.raises(ValueError):
        PluginManifest.validate_semver("abc")


# --- 2. Lifecycle Transitions & State Machine Tests ---


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.plugins.validate_plugin_by_id")
@patch("src.api.v1.routers.plugins.approve_plugin_by_id")
@patch("src.api.v1.routers.plugins.disable_plugin_by_id")
@patch("src.api.v1.routers.plugins.deprecate_plugin_by_id")
async def test_lifecycle_transitions(
    mock_deprecate: MagicMock,
    mock_disable: MagicMock,
    mock_approve: MagicMock,
    mock_val: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_admin: User,
    mock_plugin_a: Plugin,
) -> None:
    """Test plugin validation and transitions: approve, disable, deprecate."""
    mock_get_user.return_value = mock_admin
    mock_val.return_value = True

    # Mock Approve
    p_approved = Plugin()
    p_approved.id = PLUGIN_A_ID
    p_approved.name = mock_plugin_a.name
    p_approved.version = mock_plugin_a.version
    p_approved.manifest = mock_plugin_a.manifest
    p_approved.state = "approved"
    p_approved.installed_at = mock_plugin_a.installed_at
    mock_approve.return_value = p_approved

    headers = get_auth_header(ADMIN_ID, "admin")

    # 1. Trigger Validation
    res_val = await client.post(
        f"/api/v1/plugins/{PLUGIN_A_ID}/validate", headers=headers
    )
    assert res_val.status_code == 200
    assert res_val.json()["data"] is True

    # 2. Approve
    res_app = await client.post(
        f"/api/v1/plugins/{PLUGIN_A_ID}/approve", headers=headers
    )
    assert res_app.status_code == 200
    assert res_app.json()["data"]["state"] == "approved"

    # 3. Disable
    p_disabled = Plugin()
    p_disabled.id = PLUGIN_A_ID
    p_disabled.name = mock_plugin_a.name
    p_disabled.version = mock_plugin_a.version
    p_disabled.manifest = mock_plugin_a.manifest
    p_disabled.state = "disabled"
    p_disabled.installed_at = mock_plugin_a.installed_at
    mock_disable.return_value = p_disabled
    res_dis = await client.post(
        f"/api/v1/plugins/{PLUGIN_A_ID}/disable", headers=headers
    )
    assert res_dis.status_code == 200
    assert res_dis.json()["data"]["state"] == "disabled"

    # 4. Deprecate
    p_dep = Plugin()
    p_dep.id = PLUGIN_A_ID
    p_dep.name = mock_plugin_a.name
    p_dep.version = mock_plugin_a.version
    p_dep.manifest = mock_plugin_a.manifest
    p_dep.state = "deprecated"
    p_dep.installed_at = mock_plugin_a.installed_at
    mock_deprecate.return_value = p_dep
    res_dep = await client.post(
        f"/api/v1/plugins/{PLUGIN_A_ID}/deprecate", headers=headers
    )
    assert res_dep.status_code == 200
    assert res_dep.json()["data"]["state"] == "deprecated"


@pytest.mark.asyncio
async def test_approval_requires_validation(mock_db) -> None:
    """Approval requires successful validation. Unvalidated plugins fail approval."""
    plugin = Plugin()
    plugin.id = PLUGIN_A_ID
    plugin.name = "mock-invalid"
    plugin.version = "1.0.0"
    plugin.manifest = {
        "name": "mock-invalid",
        "version": "1.0.0",
        # fails interface validation
        "entry_point": "src.plugins.mock_plugin:MockInvalidPlugin",
        "capabilities": ["discovery"],
        "permissions": [],
        "timeout": 30,
    }
    plugin.state = "draft"

    mock_db.get.return_value = plugin
    mock_db.execute.return_value = MagicMock()

    with pytest.raises(PluginValidationError):
        await approve_plugin_by_id(mock_db, PLUGIN_A_ID)


# --- 3. Dynamic Loading, Validation, and Executions Boundaries ---


def test_dynamic_loading() -> None:
    """Test dynamic import of base modules and verify class existence."""
    plugin_class = PluginHost.load_plugin_class(
        "src.plugins.mock_plugin:MockDiscoveryPlugin"
    )
    assert plugin_class == MockDiscoveryPlugin

    with pytest.raises(PluginValidationError):
        # Invalid class name
        PluginHost.load_plugin_class("src.plugins.mock_plugin:NonExistentClass")

    with pytest.raises(PluginValidationError):
        # Invalid module
        PluginHost.load_plugin_class("src.plugins.non_existent:Class")


def test_validation_never_executes_run() -> None:
    """Validation checks verify manifest and methods, but must NEVER invoke run()."""
    MockDiscoveryPlugin.run_called = False

    manifest = {
        "name": "mock-discovery",
        "version": "1.0.0",
        "entry_point": "src.plugins.mock_plugin:MockDiscoveryPlugin",
        "capabilities": ["discovery"],
        "permissions": ["network"],
        "timeout": 30,
    }

    success = PluginHost.validate_plugin(
        "src.plugins.mock_plugin:MockDiscoveryPlugin", manifest
    )
    assert success is True
    assert (
        MockDiscoveryPlugin.run_called is False
    )  # Assert validation did NOT trigger execution business logic


@pytest.mark.asyncio
async def test_timeout_handling(mock_db) -> None:
    """Execution timeout triggers TimeoutError, updates state, and logs failure."""
    timeout_manifest = {
        "name": "mock-timeout",
        "version": "1.0.0",
        "entry_point": "src.plugins.mock_plugin:MockTimeoutPlugin",
        "capabilities": ["discovery"],
        "permissions": [],
        "timeout": 1,  # Short timeout of 1 second
    }

    # Verify execution timeout enforcement
    with pytest.raises(PluginExecutionError) as exc_info:
        await PluginHost.run_plugin(
            db=mock_db,
            plugin_id=PLUGIN_A_ID,
            entry_point=timeout_manifest["entry_point"],
            payload={},
            timeout=1,
        )
    assert "timed out" in str(exc_info.value)


@pytest.mark.asyncio
async def test_exception_handling(mock_db) -> None:
    """Exception boundaries capture plugin runtime crashes and log plugin.failed."""
    failing_manifest = {
        "name": "mock-failing",
        "version": "1.0.0",
        "entry_point": "src.plugins.mock_plugin:MockFailingPlugin",
        "capabilities": ["discovery"],
        "permissions": [],
        "timeout": 5,
    }

    # Verify execution exception captures correctly without throwing python engine crash
    with pytest.raises(PluginExecutionError) as exc_info:
        await PluginHost.run_plugin(
            db=mock_db,
            plugin_id=PLUGIN_A_ID,
            entry_point=failing_manifest["entry_point"],
            payload={},
            timeout=5,
        )
    assert "Simulated tool crash" in str(exc_info.value)


# --- 4. Event Logging Tests ---


@pytest.mark.asyncio
async def test_plugin_event_generation(mock_db) -> None:
    """Verify registry and host operations log appropriate rows in plugin_events."""
    event = await PluginHost.log_event(
        db=mock_db,
        plugin_id=PLUGIN_A_ID,
        event_type="plugin.validated",
        correlation_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        scan_run_id=uuid.uuid4(),
        payload={"status": "success"},
    )
    assert event.event_type == "plugin.validated"
    assert event.correlation_id is not None
    assert mock_db.add.call_count >= 1


# --- 5. Workflow Execution & Integration Tests ---


@pytest.mark.asyncio
async def test_workflow_plugin_execution(mock_db) -> None:
    """Test full workflow step executing an approved plugin inside the Celery task."""
    workflow = Workflow()
    workflow.id = WF_A_ID
    workflow.name = "Workflow running Mock Discovery Tool"
    workflow.definition = {
        "steps": [{"type": "discovery", "config": {"tools": ["mock-discovery"]}}]
    }
    workflow.state = "active"

    plugin = Plugin()
    plugin.id = PLUGIN_A_ID
    plugin.name = "mock-discovery"
    plugin.manifest = {
        "name": "mock-discovery",
        "version": "1.0.0",
        "entry_point": "src.plugins.mock_plugin:MockDiscoveryPlugin",
        "capabilities": ["discovery"],
        "permissions": [],
        "timeout": 30,
    }
    plugin.state = "approved"  # approved

    run = ScanRun()
    run.id = uuid.uuid4()
    run.workflow_id = WF_A_ID
    run.scope_id = SCOPE_A_ID
    run.status = "pending"

    mock_scope = Scope()
    mock_scope.id = SCOPE_A_ID
    mock_scope.owner_id = None
    mock_scope.deleted_at = None

    # Setup database mocks inside worker task
    # Return order: workflow, run, scope, plugin (on lookup query)
    mock_db.get.side_effect = [workflow, run, mock_scope]
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = plugin
    mock_db.execute.return_value = mock_result

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db

    with patch(
        "src.infrastructure.celery.worker.AsyncSessionLocal",
        mock_session_factory,
    ):
        from src.infrastructure.celery.worker import _execute_workflow_async

        await _execute_workflow_async(WF_A_ID, run.id, SCOPE_A_ID)

    # ScanRun should transition to completed
    assert run.status == "completed"
    assert run.plugin_id == plugin.id


@pytest.mark.asyncio
async def test_disabled_plugin_execution_blocked(mock_db) -> None:
    """Worker blocks execution of disabled plugins, registers failures."""
    workflow = Workflow()
    workflow.id = WF_A_ID
    workflow.definition = {
        "steps": [{"type": "discovery", "config": {"tools": ["mock-discovery"]}}]
    }

    plugin = Plugin()
    plugin.id = PLUGIN_A_ID
    plugin.name = "mock-discovery"
    plugin.manifest = {
        "name": "mock-discovery",
        "version": "1.0.0",
        "entry_point": "src.plugins.mock_plugin:MockDiscoveryPlugin",
        "capabilities": ["discovery"],
        "permissions": [],
        "timeout": 30,
    }
    plugin.state = "disabled"  # disabled

    run = ScanRun()
    run.id = uuid.uuid4()
    run.status = "pending"

    mock_scope = Scope()
    mock_scope.id = SCOPE_A_ID
    # Since workflow has no owner_id in this test, match it
    mock_scope.owner_id = None
    mock_scope.deleted_at = None

    mock_db.get.side_effect = [workflow, run, mock_scope]
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = plugin
    mock_db.execute.return_value = mock_result

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db

    with patch(
        "src.infrastructure.celery.worker.AsyncSessionLocal",
        mock_session_factory,
    ):
        from src.infrastructure.celery.worker import _execute_workflow_async

        await _execute_workflow_async(WF_A_ID, run.id, SCOPE_A_ID)

    # ScanRun must fail because plugin is disabled
    assert run.status == "failed"

    # Assert workflow.failed event was registered
    added_workflow_events = [
        call_args[0][0]
        for call_args in mock_db.add.call_args_list
        if isinstance(call_args[0][0], WorkflowEvent)
    ]
    failed_events = [
        e for e in added_workflow_events if e.event_type == "workflow.failed"
    ]
    assert len(failed_events) == 1
    assert "Must be approved" in failed_events[0].payload["error"]


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.workflows.get_workflow_by_id")
@patch("src.api.v1.routers.workflows.check_workflow_ownership")
async def test_deprecated_plugin_usage_blocked(
    mock_ownership: MagicMock,
    mock_get_wf: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_admin: User,
    mock_db,
) -> None:
    """Cannot attach a deprecated plugin to a new workflow."""
    # Mock database to return a deprecated plugin
    dep_plugin = Plugin()
    dep_plugin.name = "mock-deprecated"
    dep_plugin.state = "deprecated"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = dep_plugin
    mock_db.execute.return_value = mock_result

    mock_get_user.return_value = mock_admin
    payload = {
        "name": "Deprecated Testing Workflow",
        "definition": {
            "steps": [{"type": "discovery", "config": {"tools": ["mock-deprecated"]}}]
        },
    }
    headers = get_auth_header(ADMIN_ID, "admin")
    response = await client.post("/api/v1/workflows", json=payload, headers=headers)

    # Creation must fail with HTTP 400 Bad Request
    assert response.status_code == 400
    assert "deprecated" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_capability_mismatch_rejection(mock_db) -> None:
    """Capability mismatch fails scan run."""
    workflow = Workflow()
    workflow.id = WF_A_ID
    workflow.definition = {
        "steps": [
            {
                "type": "port-scan",  # step type is port-scan
                "config": {"tools": ["mock-discovery"]},
            }
        ]
    }

    plugin = Plugin()
    plugin.id = PLUGIN_A_ID
    plugin.name = "mock-discovery"
    plugin.manifest = {
        "name": "mock-discovery",
        "version": "1.0.0",
        "entry_point": "src.plugins.mock_plugin:MockDiscoveryPlugin",
        "capabilities": ["discovery"],  # capability is only discovery
        "permissions": [],
        "timeout": 30,
    }
    plugin.state = "approved"

    run = ScanRun()
    run.id = uuid.uuid4()
    run.status = "pending"

    mock_scope = Scope()
    mock_scope.id = SCOPE_A_ID
    mock_scope.owner_id = None
    mock_scope.deleted_at = None

    mock_db.get.side_effect = [workflow, run, mock_scope]
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = plugin
    mock_db.execute.return_value = mock_result

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db

    with patch(
        "src.infrastructure.celery.worker.AsyncSessionLocal",
        mock_session_factory,
    ):
        from src.infrastructure.celery.worker import _execute_workflow_async

        await _execute_workflow_async(WF_A_ID, run.id, SCOPE_A_ID)

    # Must fail because step port-scan doesn't match plugin capability discovery
    assert run.status == "failed"

    # Assert workflow.failed event exists
    added_workflow_events = [
        call_args[0][0]
        for call_args in mock_db.add.call_args_list
        if isinstance(call_args[0][0], WorkflowEvent)
    ]
    failed_events = [
        e for e in added_workflow_events if e.event_type == "workflow.failed"
    ]
    assert len(failed_events) == 1
    assert "Capability mismatch" in failed_events[0].payload["error"]


@pytest.mark.asyncio
async def test_workflow_failure_on_plugin_failure(mock_db) -> None:
    """Plugin failure results in overall workflow and scan run failing."""
    workflow = Workflow()
    workflow.id = WF_A_ID
    workflow.definition = {
        "steps": [{"type": "discovery", "config": {"tools": ["mock-failing"]}}]
    }

    plugin = Plugin()
    plugin.id = PLUGIN_A_ID
    plugin.name = "mock-failing"
    plugin.manifest = {
        "name": "mock-failing",
        "version": "1.0.0",
        "entry_point": "src.plugins.mock_plugin:MockFailingPlugin",
        "capabilities": ["discovery"],
        "permissions": [],
        "timeout": 30,
    }
    plugin.state = "approved"

    run = ScanRun()
    run.id = uuid.uuid4()
    run.status = "pending"

    mock_scope = Scope()
    mock_scope.id = SCOPE_A_ID
    mock_scope.owner_id = None
    mock_scope.deleted_at = None

    mock_db.get.side_effect = [workflow, run, mock_scope]
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = plugin
    mock_db.execute.return_value = mock_result

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db

    with patch(
        "src.infrastructure.celery.worker.AsyncSessionLocal",
        mock_session_factory,
    ):
        from src.infrastructure.celery.worker import _execute_workflow_async

        await _execute_workflow_async(WF_A_ID, run.id, SCOPE_A_ID)

    # Must fail because plugin execution raised exception
    assert run.status == "failed"

    # Assert workflow.failed event exists
    added_workflow_events = [
        call_args[0][0]
        for call_args in mock_db.add.call_args_list
        if isinstance(call_args[0][0], WorkflowEvent)
    ]
    failed_events = [
        e for e in added_workflow_events if e.event_type == "workflow.failed"
    ]
    assert len(failed_events) == 1
    assert "Plugin execution crashed" in failed_events[0].payload["error"]
