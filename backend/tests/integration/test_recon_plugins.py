import subprocess
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from src.infrastructure.database.models import (
    Asset,
    AssetHistory,
    Plugin,
    ScanRun,
    Scope,
    Workflow,
    WorkflowEvent,
)
from src.plugins.amass import AmassPlugin
from src.plugins.assetfinder import AssetfinderPlugin
from src.plugins.executor import ToolExecutionConfig, ToolExecutor
from src.plugins.host import PluginExecutionError
from src.plugins.subfinder import SubfinderPlugin
from src.plugins.theharvester import TheHarvesterPlugin
from src.services.asset_service import process_discovered_assets
from src.services.discovery_normalization_service import DiscoveryNormalizationService

# Standard UUIDs for deterministic testing
USER_A_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SCOPE_A_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
WF_A_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SCAN_RUN_A_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
PLUGIN_A_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")


@pytest.fixture
def mock_scope() -> Scope:
    s = Scope()
    s.id = SCOPE_A_ID
    s.owner_id = USER_A_ID
    s.name = "Test Scope"
    s.type = "domain"
    s.definition = {"domains": ["example.com"]}
    s.deleted_at = None
    return s


@pytest.fixture
def mock_workflow() -> Workflow:
    w = Workflow()
    w.id = WF_A_ID
    w.owner_id = USER_A_ID
    w.name = "Recon Workflow"
    w.definition = {
        "steps": [
            {
                "type": "discovery",
                "tool": "SubfinderPlugin",
                "config": {"timeout": 30},
            }
        ]
    }
    w.state = "active"
    return w


@pytest.fixture
def mock_scan_run() -> ScanRun:
    sr = ScanRun()
    sr.id = SCAN_RUN_A_ID
    sr.workflow_id = WF_A_ID
    sr.scope_id = SCOPE_A_ID
    sr.type = "discovery"
    sr.status = "pending"
    return sr


# --- 1. Plugin Execution Tests ---


@pytest.mark.asyncio
@patch("src.plugins.executor.ToolExecutor.execute")
async def test_subfinder_plugin_run(mock_exec) -> None:
    mock_res = MagicMock()
    mock_res.stdout = "api.example.com\nwww.example.com\n"
    mock_exec.return_value = mock_res

    plugin = SubfinderPlugin()
    payload = {"definition": {"domains": ["example.com"]}, "config": {"timeout": 10}}
    res = plugin.run(payload)

    assert res["tool"] == "subfinder"
    assert "api.example.com" in res["raw_output"]
    assert mock_exec.call_count == 1
    # Check config parameter passing
    args, kwargs = mock_exec.call_args
    assert args[0] == ["subfinder", "-d", "example.com", "-silent"]
    assert args[1].timeout == 10


@pytest.mark.asyncio
@patch("src.plugins.executor.ToolExecutor.execute")
async def test_amass_plugin_run(mock_exec) -> None:
    mock_res = MagicMock()
    mock_res.stdout = "api.example.com\n"
    mock_exec.return_value = mock_res

    plugin = AmassPlugin()
    payload = {"definition": {"domains": ["example.com"]}}
    res = plugin.run(payload)

    assert res["tool"] == "amass"
    assert "api.example.com" in res["raw_output"]
    args, kwargs = mock_exec.call_args
    assert args[0] == ["amass", "enum", "-d", "example.com", "-passive"]


@pytest.mark.asyncio
@patch("src.plugins.executor.ToolExecutor.execute")
async def test_assetfinder_plugin_run(mock_exec) -> None:
    mock_res = MagicMock()
    mock_res.stdout = "www.example.com\n"
    mock_exec.return_value = mock_res

    plugin = AssetfinderPlugin()
    payload = {"definition": {"domains": ["example.com"]}}
    res = plugin.run(payload)

    assert res["tool"] == "assetfinder"
    assert "www.example.com" in res["raw_output"]
    args, kwargs = mock_exec.call_args
    assert args[0] == ["assetfinder", "--subs-only", "example.com"]


@pytest.mark.asyncio
@patch("src.plugins.executor.ToolExecutor.execute")
async def test_theharvester_plugin_run(mock_exec) -> None:
    mock_res = MagicMock()
    mock_res.stdout = "contact@example.com\n"
    mock_exec.return_value = mock_res

    plugin = TheHarvesterPlugin()
    payload = {"definition": {"domains": ["example.com"]}}
    res = plugin.run(payload)

    assert res["tool"] == "theharvester"
    assert "contact@example.com" in res["raw_output"]
    args, kwargs = mock_exec.call_args
    assert args[0] == ["theHarvester", "-d", "example.com", "-b", "crtsh"]


# --- 2. Output Normalization & Confidence Scores ---


def test_output_normalization() -> None:
    # Test Subfinder normalization (plain lines)
    raw_subfinder = "api.example.com\nwww.example.com\nhostname-only\n"
    normalized = DiscoveryNormalizationService.normalize(
        "SubfinderPlugin", raw_subfinder
    )
    assert len(normalized) == 3
    assert normalized[0]["asset_type"] == "subdomain"
    assert normalized[0]["value"] == "api.example.com"
    assert normalized[0]["source_plugin"] == "SubfinderPlugin"
    assert isinstance(normalized[0]["confidence"], float)
    assert normalized[0]["confidence"] == 0.9
    assert normalized[2]["asset_type"] == "hostname"

    # Test theHarvester normalization (section headings)
    raw_harvester = """
[*] Emails found:
admin@example.com
info@example.com

[*] Hosts found:
api.example.com:1.1.1.1
dev.example.com:2.2.2.2
plain-host.example.com

[*] IPs found:
3.3.3.3
"""
    normalized_h = DiscoveryNormalizationService.normalize(
        "TheHarvesterPlugin", raw_harvester
    )
    # 2 emails, 2 hosts (host + ip) + 1 plain-host, 1 ip = 2 + (2*2) + 1 + 1 = 8 assets
    assert len(normalized_h) == 8

    emails = [x for x in normalized_h if x["asset_type"] == "email"]
    ips = [x for x in normalized_h if x["asset_type"] == "ip"]
    hostnames = [x for x in normalized_h if x["asset_type"] == "hostname"]

    assert len(emails) == 2
    assert len(ips) == 3  # 1.1.1.1, 2.2.2.2, 3.3.3.3
    assert len(hostnames) == 3  # api, dev, plain-host

    assert emails[0]["confidence"] == 0.6
    assert ips[0]["confidence"] == 0.9
    assert hostnames[0]["confidence"] == 0.8


# --- 3. Asset Persistence, Deduplication & Extended Metadata ---


@pytest.mark.asyncio
async def test_asset_persistence_new(mock_db) -> None:
    # Process a single new subdomain discovered by Subfinder
    assets_list = [
        {
            "asset_type": "subdomain",
            "value": "api.example.com",
            "source_plugin": "SubfinderPlugin",
            "confidence": 0.9,
            "metadata": {"raw_value": "api.example.com"},
        }
    ]

    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    await process_discovered_assets(
        db=mock_db,
        scope_id=SCOPE_A_ID,
        assets_list=assets_list,
        scan_run_id=SCAN_RUN_A_ID,
        workflow_id=WF_A_ID,
        actor_id=USER_A_ID,
    )

    # Added items: Asset, AssetHistory, WorkflowEvent
    # Plus AuditLog (via create_audit_entry)
    # Verify commit count
    assert mock_db.commit.call_count >= 2


@pytest.mark.asyncio
async def test_duplicate_asset_discovered_by_multiple_plugins(mock_db) -> None:
    # 1. Existing asset discovered by subfinder
    existing_asset = Asset()
    existing_asset.id = uuid.uuid4()
    existing_asset.scope_id = SCOPE_A_ID
    existing_asset.fingerprint = "subdomain:api.example.com"
    existing_asset.host = "api.example.com"
    existing_asset.asset_type = "subdomain"
    existing_asset.metadata_json = {
        "discovery_sources": [
            {
                "plugin": "subfinder",
                "first_seen": "2026-06-12T00:00:00Z",
                "last_seen": "2026-06-12T00:00:00Z",
                "confidence": 0.9,
            }
        ],
        "confidence": 0.9,
    }
    existing_asset.last_seen = datetime.now(timezone.utc)

    # Mock DB return of existing asset
    mock_db.execute.return_value.scalar_one_or_none.return_value = existing_asset

    # Discovered again by Amass with confidence 0.85
    new_discovery = [
        {
            "asset_type": "subdomain",
            "value": "api.example.com",
            "source_plugin": "AmassPlugin",
            "confidence": 0.85,
            "metadata": {"raw_value": "api.example.com"},
        }
    ]

    await process_discovered_assets(
        db=mock_db,
        scope_id=SCOPE_A_ID,
        assets_list=new_discovery,
        scan_run_id=SCAN_RUN_A_ID,
        workflow_id=WF_A_ID,
        actor_id=USER_A_ID,
    )

    # Verify discovery sources contains both subfinder and amass
    sources = existing_asset.metadata_json["discovery_sources"]
    assert len(sources) == 2
    assert sources[0]["plugin"] == "subfinder"
    assert sources[1]["plugin"] == "amass"
    assert existing_asset.metadata_json["confidence"] == 0.9  # max(0.9, 0.85)

    # Verifying history and event generation calls
    added_history = [
        x[0][0] for x in mock_db.add.call_args_list if isinstance(x[0][0], AssetHistory)
    ]
    added_events = [
        x[0][0]
        for x in mock_db.add.call_args_list
        if isinstance(x[0][0], WorkflowEvent)
    ]

    assert len(added_history) == 1
    assert added_history[0].change_type == "update"
    assert len(added_events) == 1
    assert added_events[0].event_type == "asset.source_added"


@pytest.mark.asyncio
async def test_asset_confidence_update(mock_db) -> None:
    # 1. Existing asset discovered by low confidence source (e.g. amass = 0.5)
    existing_asset = Asset()
    existing_asset.id = uuid.uuid4()
    existing_asset.scope_id = SCOPE_A_ID
    existing_asset.fingerprint = "subdomain:api.example.com"
    existing_asset.host = "api.example.com"
    existing_asset.asset_type = "subdomain"
    existing_asset.metadata_json = {
        "discovery_sources": [
            {
                "plugin": "amass",
                "first_seen": "2026-06-12T00:00:00Z",
                "last_seen": "2026-06-12T00:00:00Z",
                "confidence": 0.5,
            }
        ],
        "confidence": 0.5,
    }
    existing_asset.last_seen = datetime.now(timezone.utc)

    mock_db.execute.return_value.scalar_one_or_none.return_value = existing_asset

    # Discovered again by Subfinder with confidence 0.9
    new_discovery = [
        {
            "asset_type": "subdomain",
            "value": "api.example.com",
            "source_plugin": "SubfinderPlugin",
            "confidence": 0.9,
            "metadata": {"raw_value": "api.example.com"},
        }
    ]

    await process_discovered_assets(
        db=mock_db,
        scope_id=SCOPE_A_ID,
        assets_list=new_discovery,
        scan_run_id=SCAN_RUN_A_ID,
        workflow_id=WF_A_ID,
        actor_id=USER_A_ID,
    )

    # Overall confidence must be aggregate max of all sources: max(0.5, 0.9) = 0.9
    assert existing_asset.metadata_json["confidence"] == 0.9


# --- 4. Pre-execution Scope Validation Gates ---


@pytest.mark.asyncio
async def test_workflow_validation_deleted_scope(
    mock_db, mock_workflow, mock_scan_run, mock_scope
) -> None:
    # Scope is soft-deleted
    mock_scope.deleted_at = datetime.now(timezone.utc)

    mock_db.get.side_effect = [mock_workflow, mock_scan_run, mock_scope]

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db

    with patch(
        "src.infrastructure.celery.worker.AsyncSessionLocal",
        mock_session_factory,
    ):
        from src.infrastructure.celery.worker import _execute_workflow_async

        await _execute_workflow_async(WF_A_ID, SCAN_RUN_A_ID, SCOPE_A_ID)

    # Scan run must fail, event generated
    assert mock_scan_run.status == "failed"
    added_events = [
        x[0][0]
        for x in mock_db.add.call_args_list
        if isinstance(x[0][0], WorkflowEvent)
    ]
    assert any(
        e.event_type == "workflow.failed"
        and "Scope not found or deleted" in e.payload["error"]
        for e in added_events
    )


@pytest.mark.asyncio
async def test_workflow_validation_ownership_mismatch(
    mock_db, mock_workflow, mock_scan_run, mock_scope
) -> None:
    # Scope owner is different from workflow owner
    mock_scope.owner_id = uuid.uuid4()

    mock_db.get.side_effect = [mock_workflow, mock_scan_run, mock_scope]

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db

    with patch(
        "src.infrastructure.celery.worker.AsyncSessionLocal",
        mock_session_factory,
    ):
        from src.infrastructure.celery.worker import _execute_workflow_async

        await _execute_workflow_async(WF_A_ID, SCAN_RUN_A_ID, SCOPE_A_ID)

    # Scan run must fail, ownership mismatch event generated
    assert mock_scan_run.status == "failed"
    added_events = [
        x[0][0]
        for x in mock_db.add.call_args_list
        if isinstance(x[0][0], WorkflowEvent)
    ]
    assert any(
        e.event_type == "workflow.failed"
        and "Scope ownership mismatch" in e.payload["error"]
        for e in added_events
    )


# --- 5. ToolExecutor Exception and Timeout Handling ---


def test_tool_executor_success() -> None:
    with patch("subprocess.run") as mock_run:
        mock_completed = MagicMock()
        mock_completed.returncode = 0
        mock_completed.stdout = "output"
        mock_run.return_value = mock_completed

        config = ToolExecutionConfig(timeout=30)
        res = ToolExecutor.execute(["tool", "arg"], config)
        assert res.stdout == "output"
        assert mock_run.call_args[1]["timeout"] == 30


def test_tool_executor_timeout() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["tool"], timeout=10)

        config = ToolExecutionConfig(timeout=10)
        with pytest.raises(PluginExecutionError) as exc:
            ToolExecutor.execute(["tool"], config)
        assert "timed out" in str(exc.value)


def test_tool_executor_failure_code() -> None:
    with patch("subprocess.run") as mock_run:
        mock_completed = MagicMock()
        mock_completed.returncode = 1
        mock_completed.stderr = "error logs"
        mock_run.return_value = mock_completed

        config = ToolExecutionConfig(timeout=10)
        with pytest.raises(PluginExecutionError) as exc:
            ToolExecutor.execute(["tool"], config)
        assert "failed with code 1" in str(exc.value)


# --- 6. Event Schema Telemetry requirements ---


@pytest.mark.asyncio
async def test_event_schema_fields(mock_db) -> None:
    # Generate Workflow Event and assert presence of all required telemetry fields
    assets_list = [
        {
            "asset_type": "subdomain",
            "value": "api.example.com",
            "source_plugin": "SubfinderPlugin",
            "confidence": 0.9,
            "metadata": {},
        }
    ]
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    await process_discovered_assets(
        db=mock_db,
        scope_id=SCOPE_A_ID,
        assets_list=assets_list,
        scan_run_id=SCAN_RUN_A_ID,
        workflow_id=WF_A_ID,
        actor_id=USER_A_ID,
    )

    added_events = [
        x[0][0]
        for x in mock_db.add.call_args_list
        if isinstance(x[0][0], WorkflowEvent)
    ]

    assert len(added_events) >= 1
    event = added_events[0]
    # Check fields in database columns and payload JSON representation
    assert event.correlation_id == SCAN_RUN_A_ID
    assert event.workflow_id == WF_A_ID
    assert event.payload["correlation_id"] == str(SCAN_RUN_A_ID)
    assert event.payload["workflow_id"] == str(WF_A_ID)
    assert event.payload["scan_run_id"] == str(SCAN_RUN_A_ID)
    assert "event_id" in event.payload
    assert "timestamp" in event.payload


# --- 7. Worker Stability Test ---


@pytest.mark.asyncio
async def test_worker_stability_on_plugin_exception(
    mock_db, mock_workflow, mock_scan_run, mock_scope
) -> None:
    # If plugin raises exception, worker transitions run to failed
    # but doesn't throw raw error out
    plugin = Plugin()
    plugin.id = PLUGIN_A_ID
    plugin.name = "SubfinderPlugin"
    plugin.manifest = {
        "name": "SubfinderPlugin",
        "version": "1.0.0",
        "entry_point": "src.plugins.subfinder:SubfinderPlugin",
        "capabilities": ["discovery"],
        "timeout": 30,
    }
    plugin.state = "approved"

    mock_db.get.side_effect = [mock_workflow, mock_scan_run, mock_scope]

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = plugin
    mock_db.execute.return_value = mock_result

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db

    with patch(
        "src.infrastructure.celery.worker.AsyncSessionLocal",
        mock_session_factory,
    ):
        with patch("src.plugins.host.PluginHost.run_plugin") as mock_run:
            mock_run.side_effect = PluginExecutionError("Subprocess execution failed")

            from src.infrastructure.celery.worker import _execute_workflow_async

            # Must execute and return without throwing to caller
            await _execute_workflow_async(WF_A_ID, SCAN_RUN_A_ID, SCOPE_A_ID)

    assert mock_scan_run.status == "failed"
