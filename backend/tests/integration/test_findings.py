import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.infrastructure.database.models import (
    Asset,
    AssetPort,
    AssetService,
    AuditLog,
    Base,
    Finding,
    FindingEvidence,
    FindingHistory,
    Plugin,
    ScanRun,
    Scope,
    User,
    Workflow,
    WorkflowEvent,
)
from src.services.finding_evidence_service import FindingEvidenceService
from src.services.finding_fingerprint_service import FindingFingerprintService
from src.services.finding_normalization_service import FindingNormalizationService
from src.services.finding_service import FindingService
from src.services.finding_severity_rules import FindingSeverityRules
from src.services.finding_snapshot_service import FindingSnapshotService
from src.services.template_tracking_service import TemplateTrackingService

# Mock SQLite Database
engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine.sync_engine, "connect")
def sqlite_connect(dbapi_connection, connection_record):
    dbapi_connection.create_function(
        "now", 0, lambda: datetime.now(timezone.utc).isoformat()
    )
    dbapi_connection.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))


@event.listens_for(Base, "init", propagate=True)
def init_uuid(target, args, kwargs):
    if not hasattr(target, "id") or target.id is None:
        target.id = uuid.uuid4()


TestSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture
async def seeded_db():
    async with engine.begin() as conn:
        from sqlalchemy.dialects import sqlite
        from sqlalchemy.types import JSON, String

        for table in Base.metadata.sorted_tables:
            for column in table.columns:
                if type(column.type).__name__ == "JSONB":
                    column.type = JSON().with_variant(sqlite.JSON(), "sqlite")
                elif type(column.type).__name__ == "INET":
                    column.type = String().with_variant(sqlite.TEXT(), "sqlite")

        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    with (
        patch("src.infrastructure.celery.worker.AsyncSessionLocal", TestSessionLocal),
        patch(
            "src.infrastructure.database.session.AsyncSessionLocal",
            TestSessionLocal,
        ),
        patch("src.api.v1.routers.findings.get_db", new=TestSessionLocal),
    ):
        async with TestSessionLocal() as db:
            user_id = uuid.uuid4()
            user = User(
                id=user_id,
                email="test@aegisx.local",
                username="testuser",
                role="admin",
                password_hash="mock",
            )
            db.add(user)

            scope_id = uuid.uuid4()
            scope = Scope(
                id=scope_id,
                owner_id=user_id,
                name="Test Scope",
                type="external",
                definition={
                    "domains": ["example.com"],
                    "ips": ["192.168.1.100"],
                },
            )
            db.add(scope)

            asset = Asset(
                scope_id=scope_id,
                host="example.com",
                ip="192.168.1.100",
                asset_type="domain",
            )
            db.add(asset)
            await db.commit()
            await db.refresh(asset)

            # Add port & service for Change 8 (vulnerability-scan pre-scan check)
            port = AssetPort(
                asset_id=asset.id,
                port=80,
                protocol="tcp",
                state="open",
            )
            db.add(port)
            await db.commit()
            await db.refresh(port)

            service = AssetService(
                asset_port_id=port.id,
                service_name="http",
                product="nginx",
                version="1.18",
                confidence=1.0,
            )
            db.add(service)
            await db.commit()

            yield {
                "user_id": user_id,
                "scope_id": scope_id,
                "asset_id": asset.id,
                "port_id": port.id,
                "service_id": service.id,
            }


def mock_nuclei_raw_json():
    item = {
        "template-id": "http-missing-security-headers",
        "info": {
            "name": "Missing Security Headers",
            "severity": "info",
            "description": "Checks for missing security headers",
        },
        "type": "http",
        "host": "http://example.com:80",
        "matched-at": "http://example.com:80/login",
        "matcher-name": "x-frame-options",
        "matcher-value": "missing",
        "curl-command": "curl -X GET http://example.com:80/login",
        "request": "GET /login HTTP/1.1\r\n\r\n",
        "response": "HTTP/1.1 200 OK\r\n\r\n",
    }
    return json.dumps(item)


# 1. Nuclei plugin execution
@pytest.mark.asyncio
async def test_nuclei_plugin_execution():
    from src.plugins.nuclei import NucleiPlugin

    plugin = NucleiPlugin()
    assert plugin.initialize() is True
    assert plugin.validate() is True
    assert plugin.health_check() is True

    payload = {
        "config": {"target": "http://example.com", "templates": ["cves"]},
    }

    mock_completed_proc = MagicMock()
    mock_completed_proc.stdout = "nuclei output"
    mock_completed_proc.returncode = 0

    with patch(
        "src.plugins.executor.ToolExecutor.execute",
        return_value=mock_completed_proc,
    ) as mock_exec:
        res = plugin.run(payload)
        assert res["raw_output"] == "nuclei output"
        mock_exec.assert_called_once()
        cmd = mock_exec.call_args[0][0]
        assert "nuclei" in cmd
        assert "-target" in cmd
        assert "http://example.com" in cmd
        assert "-json" in cmd
        assert "-silent" in cmd
        assert "-t" in cmd


# 2. JSON normalization
def test_json_normalization():
    raw_lines = (
        mock_nuclei_raw_json()
        + "\n"
        + json.dumps(
            {
                "template-id": "cve-2021-1234",
                "info": {
                    "name": "Big Exploit",
                    "severity": "CRITICAL",
                    "description": "critical vulnerability",
                },
                "type": "http",
                "host": "http://example.com:80",
            }
        )
    )

    normalized = FindingNormalizationService.normalize_nuclei(raw_lines)
    assert len(normalized) == 2
    assert normalized[0]["finding"]["severity"] == "info"
    assert normalized[0]["finding"]["template_id"] == "http-missing-security-headers"
    assert normalized[0]["evidence"]["matched_at"] == "http://example.com:80/login"
    assert normalized[0]["evidence"]["matcher_name"] == "x-frame-options"
    assert normalized[0]["evidence"]["matcher_value"] == "missing"

    assert normalized[1]["finding"]["severity"] == "critical"
    assert normalized[1]["finding"]["title"] == "Big Exploit"


# 3. Finding creation
@pytest.mark.asyncio
async def test_finding_creation(seeded_db):
    async with TestSessionLocal() as db:
        raw = mock_nuclei_raw_json()
        normalized = FindingNormalizationService.normalize_nuclei(raw)

        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        q = select(Finding).where(Finding.asset_id == seeded_db["asset_id"])
        res = await db.execute(q)
        finding = res.scalar_one()

        assert finding.title == "Missing Security Headers"
        assert finding.severity == "info"
        assert finding.status == "open"
        assert finding.template_id == "http-missing-security-headers"
        assert finding.asset_port_id == seeded_db["port_id"]
        assert finding.asset_service_id == seeded_db["service_id"]


# 4. Finding deduplication
@pytest.mark.asyncio
async def test_finding_deduplication(seeded_db):
    async with TestSessionLocal() as db:
        raw = mock_nuclei_raw_json()
        normalized = FindingNormalizationService.normalize_nuclei(raw)

        scan_id = uuid.uuid4()
        wf_id = uuid.uuid4()
        # First discovery
        await FindingService.process_discovered_findings(
            db, seeded_db["scope_id"], normalized, scan_id, wf_id, seeded_db["user_id"]
        )

        # Second discovery (should not create duplicate)
        await FindingService.process_discovered_findings(
            db, seeded_db["scope_id"], normalized, scan_id, wf_id, seeded_db["user_id"]
        )

        q = select(Finding).where(Finding.asset_id == seeded_db["asset_id"])
        res = await db.execute(q)
        findings = res.scalars().all()
        assert len(findings) == 1


# 5. Evidence persistence
@pytest.mark.asyncio
async def test_evidence_persistence(seeded_db):
    async with TestSessionLocal() as db:
        raw = mock_nuclei_raw_json()
        normalized = FindingNormalizationService.normalize_nuclei(raw)

        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        q_find = select(Finding).where(Finding.asset_id == seeded_db["asset_id"])
        res_find = await db.execute(q_find)
        finding = res_find.scalar_one()

        q_ev = select(FindingEvidence).where(FindingEvidence.finding_id == finding.id)
        res_ev = await db.execute(q_ev)
        evidence = res_ev.scalar_one()

        assert evidence.evidence_type == "http"
        assert evidence.matcher_name == "x-frame-options"
        assert evidence.matcher_value == "missing"
        assert evidence.evidence_hash is not None


# 6. Severity mapping
def test_severity_mapping():
    assert FindingSeverityRules.normalize_severity("INFO") == "info"
    assert FindingSeverityRules.normalize_severity("critical") == "critical"
    assert FindingSeverityRules.normalize_severity("HIGH") == "high"
    assert FindingSeverityRules.normalize_severity("MEDIUM") == "medium"
    assert FindingSeverityRules.normalize_severity("low") == "low"
    assert FindingSeverityRules.normalize_severity("unknown-sev") == "info"

    assert FindingSeverityRules.severity_rank("critical") == 5
    assert FindingSeverityRules.severity_rank("info") == 1

    assert FindingSeverityRules.is_valid_severity("HIGH") is True
    assert FindingSeverityRules.is_valid_severity("invalid") is False


# 7. Lifecycle transitions
@pytest.mark.asyncio
async def test_lifecycle_transitions(seeded_db):
    async with TestSessionLocal() as db:
        raw = mock_nuclei_raw_json()
        normalized = FindingNormalizationService.normalize_nuclei(raw)

        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        q = select(Finding).where(Finding.asset_id == seeded_db["asset_id"])
        res = await db.execute(q)
        finding = res.scalar_one()

        # Transition to acknowledged
        updated = await FindingService.update_status(
            db, finding.id, "acknowledged", seeded_db["user_id"]
        )
        assert updated.status == "acknowledged"

        # Transition to resolved
        updated = await FindingService.update_status(
            db, finding.id, "resolved", seeded_db["user_id"]
        )
        assert updated.status == "resolved"


# 8. History generation
@pytest.mark.asyncio
async def test_history_generation(seeded_db):
    async with TestSessionLocal() as db:
        raw = mock_nuclei_raw_json()
        normalized = FindingNormalizationService.normalize_nuclei(raw)

        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        q = select(Finding).where(Finding.asset_id == seeded_db["asset_id"])
        res = await db.execute(q)
        finding = res.scalar_one()

        # Change status and trigger history
        await FindingService.update_status(
            db, finding.id, "resolved", seeded_db["user_id"]
        )

        q_hist = (
            select(FindingHistory)
            .where(FindingHistory.finding_id == finding.id)
            .order_by(FindingHistory.created_at.desc())
        )
        res_hist = await db.execute(q_hist)
        history_records = res_hist.scalars().all()

        assert len(history_records) >= 2  # create and status_change
        status_change = history_records[0]
        assert status_change.change_type == "status_change"
        assert status_change.old_value == {"status": "open"}
        assert status_change.new_value == {"status": "resolved"}


# 9. Audit generation
@pytest.mark.asyncio
async def test_audit_generation(seeded_db):
    async with TestSessionLocal() as db:
        raw = mock_nuclei_raw_json()
        normalized = FindingNormalizationService.normalize_nuclei(raw)

        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        q_audit = select(AuditLog).where(AuditLog.target_type == "finding")
        res_audit = await db.execute(q_audit)
        audit_logs = res_audit.scalars().all()

        assert len(audit_logs) >= 1
        assert audit_logs[0].action == "create_finding"


# 10. Event generation
@pytest.mark.asyncio
async def test_event_generation(seeded_db):
    async with TestSessionLocal() as db:
        raw = mock_nuclei_raw_json()
        normalized = FindingNormalizationService.normalize_nuclei(raw)

        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        q_evt = select(WorkflowEvent).where(
            WorkflowEvent.event_type == "finding.discovered"
        )
        res_evt = await db.execute(q_evt)
        events = res_evt.scalars().all()

        assert len(events) == 1
        payload = events[0].payload
        assert payload["finding_id"] is not None
        assert payload["severity"] == "info"
        assert payload["template_id"] == "http-missing-security-headers"


# 11. Workflow integration
@pytest.mark.asyncio
async def test_workflow_integration(seeded_db):
    # Setup workflow and celery worker context
    from src.infrastructure.celery.worker import _execute_workflow_async

    wf_definition = {
        "steps": [
            {
                "type": "vulnerability-scan",
                "tool": "NucleiPlugin",
                "config": {"target": "http://example.com:80"},
            }
        ]
    }

    async with TestSessionLocal() as db:
        wf = Workflow(
            owner_id=seeded_db["user_id"],
            name="Vuln Scan Workflow",
            definition=wf_definition,
            state="draft",
        )
        db.add(wf)

        plugin = Plugin(
            name="NucleiPlugin",
            version="1.0.0",
            manifest={
                "name": "NucleiPlugin",
                "version": "1.0.0",
                "entry_point": "src.plugins.nuclei:NucleiPlugin",
                "capabilities": ["vulnerability-scan"],
                "permissions": [],
                "timeout": 30,
            },
            state="approved",
        )
        db.add(plugin)
        await db.commit()

        run = ScanRun(
            workflow_id=wf.id,
            scope_id=seeded_db["scope_id"],
            type="nuclei",
            status="pending",
        )
        db.add(run)
        await db.commit()

        # Run worker with mocked Nuclei Plugin execution returning findings
        mock_result = {"raw_output": mock_nuclei_raw_json()}
        with patch(
            "src.plugins.host.PluginHost.run_plugin",
            return_value=mock_result,
        ):
            await _execute_workflow_async(wf.id, run.id, seeded_db["scope_id"])

        await db.refresh(run)
        assert run.status == "completed"

        # Verify finding exists
        q = select(Finding).where(Finding.asset_id == seeded_db["asset_id"])
        res = await db.execute(q)
        findings = res.scalars().all()
        assert len(findings) == 1
        assert findings[0].template_id == "http-missing-security-headers"


# 12. Capability mismatch rejection
@pytest.mark.asyncio
async def test_capability_mismatch_rejection(seeded_db):
    from src.infrastructure.celery.worker import _execute_workflow_async

    # Workflow step expects port-scan capability from Nuclei (mismatch)
    wf_definition = {
        "steps": [
            {
                "type": "port-scan",
                "tool": "NucleiPlugin",
            }
        ]
    }

    async with TestSessionLocal() as db:
        wf = Workflow(
            owner_id=seeded_db["user_id"],
            name="Mismatched Workflow",
            definition=wf_definition,
            state="draft",
        )
        db.add(wf)

        plugin = Plugin(
            name="NucleiPlugin",
            version="1.0.0",
            manifest={
                "name": "NucleiPlugin",
                "version": "1.0.0",
                "entry_point": "src.plugins.nuclei:NucleiPlugin",
                "capabilities": ["vulnerability-scan"],
                "permissions": [],
                "timeout": 30,
            },
            state="approved",
        )
        db.add(plugin)

        run = ScanRun(
            workflow_id=wf.id,
            scope_id=seeded_db["scope_id"],
            type="nuclei",
            status="pending",
        )
        db.add(run)
        await db.commit()

        await _execute_workflow_async(wf.id, run.id, seeded_db["scope_id"])

        await db.refresh(run)
        assert run.status == "failed"

        # Assert workflow.failed is generated
        q_evt = select(WorkflowEvent).where(
            WorkflowEvent.event_type == "workflow.failed"
        )
        res_evt = await db.execute(q_evt)
        assert len(res_evt.scalars().all()) == 1


# 13. Ownership validation
@pytest.mark.asyncio
async def test_ownership_validation(seeded_db):
    from src.infrastructure.celery.worker import _execute_workflow_async

    # Scope belongs to another user
    async with TestSessionLocal() as db:
        other_user = User(
            email="other@aegisx.local",
            username="otheruser",
            role="operator",
            password_hash="mock",
        )
        db.add(other_user)
        await db.commit()

        wf = Workflow(
            owner_id=other_user.id,
            name="Unauthorized Workflow",
            definition={
                "steps": [{"type": "vulnerability-scan", "tool": "NucleiPlugin"}]
            },
            state="draft",
        )
        db.add(wf)

        run = ScanRun(
            workflow_id=wf.id,
            scope_id=seeded_db["scope_id"],  # scope owned by seeded_db["user_id"]
            type="nuclei",
            status="pending",
        )
        db.add(run)
        await db.commit()

        await _execute_workflow_async(wf.id, run.id, seeded_db["scope_id"])

        await db.refresh(run)
        assert run.status == "failed"

        q_evt = select(WorkflowEvent).where(
            WorkflowEvent.event_type == "workflow.failed"
        )
        res_evt = await db.execute(q_evt)
        events = res_evt.scalars().all()
        assert any("Scope ownership mismatch" in e.payload.get("error") for e in events)


# 14. Reopen resolved finding
@pytest.mark.asyncio
async def test_reopen_resolved_finding(seeded_db):
    async with TestSessionLocal() as db:
        raw = mock_nuclei_raw_json()
        normalized = FindingNormalizationService.normalize_nuclei(raw)

        # 1. Discover finding
        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )
        q = select(Finding).where(Finding.asset_id == seeded_db["asset_id"])
        res = await db.execute(q)
        finding = res.scalar_one()

        # 2. Resolve it
        await FindingService.update_status(
            db, finding.id, "resolved", seeded_db["user_id"]
        )
        await db.refresh(finding)
        assert finding.status == "resolved"

        # 3. Rediscover it
        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )
        await db.refresh(finding)
        # Should be open again
        assert finding.status == "open"


# 15. Suppress finding
@pytest.mark.asyncio
async def test_suppress_finding(seeded_db):
    async with TestSessionLocal() as db:
        raw = mock_nuclei_raw_json()
        normalized = FindingNormalizationService.normalize_nuclei(raw)

        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )
        q = select(Finding).where(Finding.asset_id == seeded_db["asset_id"])
        res = await db.execute(q)
        finding = res.scalar_one()

        # Suppress
        await FindingService.update_status(
            db, finding.id, "suppressed", seeded_db["user_id"]
        )
        await db.refresh(finding)
        assert finding.status == "suppressed"


# 16. Template tracking
@pytest.mark.asyncio
async def test_template_tracking(seeded_db):
    async with TestSessionLocal() as db:
        raw = mock_nuclei_raw_json()
        normalized = FindingNormalizationService.normalize_nuclei(raw)

        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        stats = await TemplateTrackingService.get_template_stats(
            db, "http-missing-security-headers"
        )
        assert stats["template_id"] == "http-missing-security-headers"
        assert stats["finding_count"] == 1
        assert stats["severity_distribution"]["info"] == 1


# 17. Evidence retention
@pytest.mark.asyncio
async def test_evidence_retention(seeded_db):
    async with TestSessionLocal() as db:
        raw = mock_nuclei_raw_json()
        normalized = FindingNormalizationService.normalize_nuclei(raw)

        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )
        # Re-run scan with different response (different evidence)
        item2 = json.loads(mock_nuclei_raw_json())
        item2["response"] = "HTTP/1.1 500 Server Error\r\n\r\n"
        normalized2 = FindingNormalizationService.normalize_nuclei(json.dumps(item2))

        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized2,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        # Check that both evidence versions exist (version retention)
        q_find = select(Finding).where(Finding.asset_id == seeded_db["asset_id"])
        res_find = await db.execute(q_find)
        finding = res_find.scalar_one()

        q_ev = select(FindingEvidence).where(FindingEvidence.finding_id == finding.id)
        res_ev = await db.execute(q_ev)
        evidences = res_ev.scalars().all()

        assert len(evidences) == 2


# 18. Worker stability
@pytest.mark.asyncio
async def test_worker_stability(seeded_db):
    from src.infrastructure.celery.worker import _execute_workflow_async

    wf_definition = {
        "steps": [
            {
                "type": "vulnerability-scan",
                "tool": "NucleiPlugin",
                "config": {"target": "http://example.com:80"},
            }
        ]
    }

    async with TestSessionLocal() as db:
        wf = Workflow(
            owner_id=seeded_db["user_id"],
            name="Crashed Workflow",
            definition=wf_definition,
            state="draft",
        )
        db.add(wf)

        plugin = Plugin(
            name="NucleiPlugin",
            version="1.0.0",
            manifest={
                "name": "NucleiPlugin",
                "version": "1.0.0",
                "entry_point": "src.plugins.nuclei:NucleiPlugin",
                "capabilities": ["vulnerability-scan"],
                "permissions": [],
                "timeout": 30,
            },
            state="approved",
        )
        db.add(plugin)

        run = ScanRun(
            workflow_id=wf.id,
            scope_id=seeded_db["scope_id"],
            type="nuclei",
            status="pending",
        )
        db.add(run)
        await db.commit()

        # Force run_plugin to raise Exception
        with patch(
            "src.plugins.host.PluginHost.run_plugin",
            side_effect=Exception("Hard Plugin Crash"),
        ):
            await _execute_workflow_async(wf.id, run.id, seeded_db["scope_id"])

        await db.refresh(run)
        assert run.status == "failed"


# 19. Duplicate finding prevention
@pytest.mark.asyncio
async def test_duplicate_finding_prevention(seeded_db):
    async with TestSessionLocal() as db:
        # Creating two findings with the same fingerprint directly
        # should fail SQLite unique constraint
        f1 = Finding(
            asset_id=seeded_db["asset_id"],
            title="Finding 1",
            severity="low",
            status="open",
            template_id="t1",
            template_name="T1",
            source_plugin="NucleiPlugin",
            fingerprint="same-fp",
        )
        db.add(f1)
        await db.commit()

        f2 = Finding(
            asset_id=seeded_db["asset_id"],
            title="Finding 2",
            severity="high",
            status="open",
            template_id="t1",
            template_name="T1",
            source_plugin="NucleiPlugin",
            fingerprint="same-fp",
        )
        db.add(f2)
        with pytest.raises(Exception):
            await db.commit()


# 20. Finding fingerprint generation
def test_finding_fingerprint_generation():
    ast_id = uuid.uuid4()
    fp1 = FindingFingerprintService.generate_fingerprint(
        ast_id, "cve-1234", "example.com", "/path"
    )
    fp2 = FindingFingerprintService.generate_fingerprint(
        ast_id, "cve-1234", "example.com", "/path"
    )
    fp3 = FindingFingerprintService.generate_fingerprint(
        ast_id, "cve-1234", "example.com", "/different"
    )

    assert fp1 == fp2
    assert fp1 != fp3


# --- ADDITIONAL REQUIRED TESTS ---


# test_finding_snapshot_generation
@pytest.mark.asyncio
async def test_finding_snapshot_generation(seeded_db):
    async with TestSessionLocal() as db:
        # Seed 3 findings of different severities and status
        f1 = Finding(
            asset_id=seeded_db["asset_id"],
            title="F1",
            severity="critical",
            status="open",
            template_id="t1",
            template_name="T1",
            source_plugin="NucleiPlugin",
            fingerprint="fp1",
        )
        f2 = Finding(
            asset_id=seeded_db["asset_id"],
            title="F2",
            severity="high",
            status="acknowledged",
            template_id="t2",
            template_name="T2",
            source_plugin="NucleiPlugin",
            fingerprint="fp2",
        )
        f3 = Finding(
            asset_id=seeded_db["asset_id"],
            title="F3",
            severity="high",
            status="resolved",
            template_id="t3",
            template_name="T3",
            source_plugin="NucleiPlugin",
            fingerprint="fp3",
        )
        db.add_all([f1, f2, f3])
        await db.commit()

        # Generate snapshot
        snapshot = await FindingSnapshotService.generate_finding_snapshot(
            db, seeded_db["asset_id"]
        )

        assert snapshot["critical_count"] == 1
        assert snapshot["high_count"] == 2
        assert snapshot["medium_count"] == 0
        assert snapshot["open_count"] == 1
        assert snapshot["acknowledged_count"] == 1
        assert snapshot["resolved_count"] == 1


# test_evidence_immutability
@pytest.mark.asyncio
async def test_evidence_immutability(seeded_db):
    async with TestSessionLocal() as db:
        # Create a finding and evidence
        finding = Finding(
            asset_id=seeded_db["asset_id"],
            title="F1",
            severity="critical",
            status="open",
            template_id="t1",
            template_name="T1",
            source_plugin="NucleiPlugin",
            fingerprint="fp1",
        )
        db.add(finding)
        await db.commit()
        await db.refresh(finding)

        # 1. Create original evidence
        ev = await FindingEvidenceService.create_evidence(
            db,
            finding.id,
            "http",
            "req1",
            "res1",
            "url1",
            "matcher1",
            "val1",
        )
        orig_hash = ev.evidence_hash
        orig_id = ev.id

        # 2. Check DB remains unchanged, and new version inserts
        # another record (no UPDATE)
        # Attempt to insert same evidence details
        ev2 = await FindingEvidenceService.create_evidence(
            db,
            finding.id,
            "http",
            "req1",
            "res1",
            "url1",
            "matcher1",
            "val1",
        )
        assert ev2.id == orig_id  # Should return existing because hash matches

        # Create new evidence details (different response)
        ev3 = await FindingEvidenceService.create_evidence(
            db,
            finding.id,
            "http",
            "req1",
            "res2",  # changed
            "url1",
            "matcher1",
            "val1",
        )
        assert ev3.id != orig_id  # New ID generated
        assert ev3.evidence_hash != orig_hash

        # Verify all evidences
        q = select(FindingEvidence).where(FindingEvidence.finding_id == finding.id)
        res = await db.execute(q)
        records = res.scalars().all()
        assert len(records) == 2


# test_template_severity_distribution
@pytest.mark.asyncio
async def test_template_severity_distribution(seeded_db):
    async with TestSessionLocal() as db:
        # 2 critical, 5 high, 10 medium findings for template 't1'
        findings = []
        for i in range(2):
            findings.append(
                Finding(
                    asset_id=seeded_db["asset_id"],
                    title=f"Crit_{i}",
                    severity="critical",
                    status="open",
                    template_id="t1",
                    template_name="T1",
                    source_plugin="NucleiPlugin",
                    fingerprint=f"fp_crit_{i}",
                )
            )
        for i in range(5):
            findings.append(
                Finding(
                    asset_id=seeded_db["asset_id"],
                    title=f"High_{i}",
                    severity="high",
                    status="open",
                    template_id="t1",
                    template_name="T1",
                    source_plugin="NucleiPlugin",
                    fingerprint=f"fp_high_{i}",
                )
            )
        for i in range(10):
            findings.append(
                Finding(
                    asset_id=seeded_db["asset_id"],
                    title=f"Med_{i}",
                    severity="medium",
                    status="open",
                    template_id="t1",
                    template_name="T1",
                    source_plugin="NucleiPlugin",
                    fingerprint=f"fp_med_{i}",
                )
            )

        db.add_all(findings)
        await db.commit()

        stats = await TemplateTrackingService.get_template_stats(db, "t1")
        assert stats["finding_count"] == 17
        assert stats["severity_distribution"]["critical"] == 2
        assert stats["severity_distribution"]["high"] == 5
        assert stats["severity_distribution"]["medium"] == 10
        assert stats["severity_distribution"]["low"] == 0
        assert stats["severity_distribution"]["info"] == 0


# test_resolved_finding_reopened_by_rediscovery
@pytest.mark.asyncio
async def test_resolved_finding_reopened_by_rediscovery(seeded_db):
    async with TestSessionLocal() as db:
        raw = mock_nuclei_raw_json()
        normalized = FindingNormalizationService.normalize_nuclei(raw)

        # 1. Discover
        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )
        q = select(Finding).where(Finding.asset_id == seeded_db["asset_id"])
        res = await db.execute(q)
        finding = res.scalar_one()
        assert finding.status == "open"

        # 2. Resolve
        await FindingService.update_status(
            db, finding.id, "resolved", seeded_db["user_id"]
        )
        await db.refresh(finding)
        assert finding.status == "resolved"

        # 3. Rediscover and verify reopen triggers
        scan_id = uuid.uuid4()
        wf_id = uuid.uuid4()
        await FindingService.process_discovered_findings(
            db, seeded_db["scope_id"], normalized, scan_id, wf_id, seeded_db["user_id"]
        )
        await db.refresh(finding)

        assert finding.status == "open"

        # Verify reopened event
        q_evt = (
            select(WorkflowEvent)
            .where(
                WorkflowEvent.event_type == "finding.reopened",
                WorkflowEvent.correlation_id == scan_id,
            )
            .order_by(WorkflowEvent.timestamp.desc())
        )
        res_evt = await db.execute(q_evt)
        events = res_evt.scalars().all()
        assert len(events) == 1
        assert events[0].payload["finding_id"] == str(finding.id)

        # Verify history record
        q_hist = (
            select(FindingHistory)
            .where(
                FindingHistory.finding_id == finding.id,
                FindingHistory.change_type == "status_change",
            )
            .order_by(FindingHistory.created_at.desc())
        )
        res_hist = await db.execute(q_hist)
        histories = res_hist.scalars().all()
        assert len(histories) == 2
        assert histories[0].old_value == {"status": "resolved"}
        assert histories[0].new_value == {"status": "open"}

        # Verify audit log
        q_audit = select(AuditLog).where(
            AuditLog.target_id == finding.id, AuditLog.action == "reopen_finding"
        )
        res_audit = await db.execute(q_audit)
        audits = res_audit.scalars().all()
        assert len(audits) == 1


@pytest.mark.asyncio
async def test_finding_snapshot_trend_metrics(seeded_db):
    async with TestSessionLocal() as db:
        # 1. Create a ScanRun to associate trend calculations with
        scan_run = ScanRun(
            scope_id=seeded_db["scope_id"],
            type="vulnerability-scan",
            status="running",
            start_ts=datetime.now(timezone.utc),
        )
        db.add(scan_run)
        await db.commit()
        await db.refresh(scan_run)

        # Create 3 unique findings
        raw_list = []
        for i in range(3):
            item = json.loads(mock_nuclei_raw_json())
            item["template-id"] = f"template-{i}"
            raw_list.append(json.dumps(item))

        normalized = []
        for raw in raw_list:
            normalized.extend(FindingNormalizationService.normalize_nuclei(raw))

        # Discover 3 new findings
        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            scan_run.id,
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        # Get snapshot
        snapshot = await FindingSnapshotService.generate_finding_snapshot(
            db, seeded_db["asset_id"]
        )
        assert snapshot["new_findings_since_last_scan"] == 3
        assert snapshot["resolved_since_last_scan"] == 0
        assert snapshot["reopened_since_last_scan"] == 0

        # Resolve 1 finding
        q_find = select(Finding).where(Finding.asset_id == seeded_db["asset_id"])
        res_find = await db.execute(q_find)
        findings = res_find.scalars().all()
        target_finding = findings[0]

        await FindingService.update_status(
            db, target_finding.id, "resolved", seeded_db["user_id"]
        )

        snapshot = await FindingSnapshotService.generate_finding_snapshot(
            db, seeded_db["asset_id"]
        )
        assert snapshot["resolved_since_last_scan"] == 1

        # Rediscover the resolved finding to trigger reopen
        reopen_normalized = FindingNormalizationService.normalize_nuclei(raw_list[0])
        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            reopen_normalized,
            scan_run.id,
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        snapshot = await FindingSnapshotService.generate_finding_snapshot(
            db, seeded_db["asset_id"]
        )
        assert snapshot["reopened_since_last_scan"] == 1


@pytest.mark.asyncio
async def test_template_affected_asset_count(seeded_db):
    async with TestSessionLocal() as db:
        # Create three assets in same scope
        asset_a = Asset(
            scope_id=seeded_db["scope_id"],
            host="asset-a.example.com",
            ip="192.168.1.101",
            asset_type="domain",
        )
        asset_b = Asset(
            scope_id=seeded_db["scope_id"],
            host="asset-b.example.com",
            ip="192.168.1.102",
            asset_type="domain",
        )
        asset_c = Asset(
            scope_id=seeded_db["scope_id"],
            host="asset-c.example.com",
            ip="192.168.1.103",
            asset_type="domain",
        )
        db.add_all([asset_a, asset_b, asset_c])
        await db.commit()
        await db.refresh(asset_a)
        await db.refresh(asset_b)
        await db.refresh(asset_c)

        # Create findings using the template_id = "test-template"
        now = datetime.now(timezone.utc)

        f_a = Finding(
            asset_id=asset_a.id,
            title="Finding A",
            severity="medium",
            status="open",
            template_id="test-template",
            template_name="Test Template",
            source_plugin="NucleiPlugin",
            first_seen=now,
            last_seen=now,
            created_at=now,
            updated_at=now,
            fingerprint="fp-a",
        )
        f_b1 = Finding(
            asset_id=asset_b.id,
            title="Finding B1",
            severity="medium",
            status="open",
            template_id="test-template",
            template_name="Test Template",
            source_plugin="NucleiPlugin",
            first_seen=now,
            last_seen=now,
            created_at=now,
            updated_at=now,
            fingerprint="fp-b1",
        )
        f_b2 = Finding(
            asset_id=asset_b.id,
            title="Finding B2",
            severity="medium",
            status="open",
            template_id="test-template",
            template_name="Test Template",
            source_plugin="NucleiPlugin",
            first_seen=now,
            last_seen=now,
            created_at=now,
            updated_at=now,
            fingerprint="fp-b2",
        )
        f_c = Finding(
            asset_id=asset_c.id,
            title="Finding C",
            severity="medium",
            status="open",
            template_id="test-template",
            template_name="Test Template",
            source_plugin="NucleiPlugin",
            first_seen=now,
            last_seen=now,
            created_at=now,
            updated_at=now,
            fingerprint="fp-c",
        )
        db.add_all([f_a, f_b1, f_b2, f_c])
        await db.commit()

        # Check template stats
        stats = await TemplateTrackingService.get_template_stats(db, "test-template")
        assert stats["affected_asset_count"] == 3


@pytest.mark.asyncio
async def test_finding_disappears_from_subsequent_scan(seeded_db):
    async with TestSessionLocal() as db:
        raw = mock_nuclei_raw_json()
        normalized = FindingNormalizationService.normalize_nuclei(raw)

        # 1. Discover the finding in Scan 1
        scan_id_1 = uuid.uuid4()
        wf_id_1 = uuid.uuid4()
        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            scan_id_1,
            wf_id_1,
            seeded_db["user_id"],
        )

        # Verify it exists and is open
        q = select(Finding).where(Finding.asset_id == seeded_db["asset_id"])
        res = await db.execute(q)
        finding = res.scalar_one()
        assert finding.status == "open"
        assert finding.metadata_json.get("closed_by_scan") is False
        assert finding.metadata_json.get("last_scan_missing") is False

        # 2. Run Scan 2 where the finding is absent
        scan_id_2 = uuid.uuid4()
        wf_id_2 = uuid.uuid4()
        processed_2 = await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            [],
            scan_id_2,
            wf_id_2,
            seeded_db["user_id"],
        )

        from src.services.finding_reconciliation_service import (
            FindingReconciliationService,
        )

        await FindingReconciliationService.reconcile_findings(
            db=db,
            scope_id=seeded_db["scope_id"],
            scan_run_id=scan_id_2,
            workflow_id=wf_id_2,
            actor_id=seeded_db["user_id"],
            source_plugin="NucleiPlugin",
            step_type="vulnerability-scan",
            step_config={},
            processed_fingerprints=processed_2,
        )

        await db.refresh(finding)

        # Verify status remains open, but metadata indicates missing
        assert finding.status == "open"
        assert finding.metadata_json.get("closed_by_scan") is True
        assert finding.metadata_json.get("last_scan_missing") is True

        # Verify history record for metadata_change
        q_hist = select(FindingHistory).where(
            FindingHistory.finding_id == finding.id,
            FindingHistory.change_type == "metadata_change",
        )
        res_hist = await db.execute(q_hist)
        histories = res_hist.scalars().all()
        assert len(histories) == 1
        assert histories[0].new_value == {
            "closed_by_scan": True,
            "last_scan_missing": True,
        }

        # Verify audit log
        q_audit = select(AuditLog).where(
            AuditLog.target_id == finding.id,
            AuditLog.action == "closed_by_scan",
        )
        res_audit = await db.execute(q_audit)
        audits = res_audit.scalars().all()
        assert len(audits) == 1

        # Verify workflow event
        q_evt = select(WorkflowEvent).where(
            WorkflowEvent.event_type == "finding.no_longer_detected",
            WorkflowEvent.correlation_id == scan_id_2,
        )
        res_evt = await db.execute(q_evt)
        events = res_evt.scalars().all()
        assert len(events) == 1


@pytest.mark.asyncio
async def test_finding_rediscovery_clears_closed_by_scan_flags(seeded_db):
    async with TestSessionLocal() as db:
        raw = mock_nuclei_raw_json()
        normalized = FindingNormalizationService.normalize_nuclei(raw)

        # 1. Discover (Scan 1)
        scan_id_1 = uuid.uuid4()
        wf_id_1 = uuid.uuid4()
        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            scan_id_1,
            wf_id_1,
            seeded_db["user_id"],
        )

        q = select(Finding).where(Finding.asset_id == seeded_db["asset_id"])
        res = await db.execute(q)
        finding = res.scalar_one()
        assert finding.status == "open"
        assert finding.metadata_json.get("closed_by_scan") is False

        # 2. Reconcile as absent (Scan 2)
        scan_id_2 = uuid.uuid4()
        wf_id_2 = uuid.uuid4()
        from src.services.finding_reconciliation_service import (
            FindingReconciliationService,
        )

        await FindingReconciliationService.reconcile_findings(
            db=db,
            scope_id=seeded_db["scope_id"],
            scan_run_id=scan_id_2,
            workflow_id=wf_id_2,
            actor_id=seeded_db["user_id"],
            source_plugin="NucleiPlugin",
            step_type="vulnerability-scan",
            step_config={},
            processed_fingerprints=[],
        )
        await db.refresh(finding)
        assert finding.metadata_json.get("closed_by_scan") is True
        assert finding.status == "open"

        # 3. Rediscover (Scan 3)
        scan_id_3 = uuid.uuid4()
        wf_id_3 = uuid.uuid4()
        await FindingService.process_discovered_findings(
            db,
            seeded_db["scope_id"],
            normalized,
            scan_id_3,
            wf_id_3,
            seeded_db["user_id"],
        )
        await db.refresh(finding)

        # Verify closed_by_scan and last_scan_missing are False,
        # and status is still open
        assert finding.metadata_json.get("closed_by_scan") is False
        assert finding.metadata_json.get("last_scan_missing") is False
        assert finding.status == "open"

        # Verify history record for metadata_change from True -> False
        q_hist = select(FindingHistory).where(
            FindingHistory.finding_id == finding.id,
            FindingHistory.change_type == "metadata_change",
            FindingHistory.new_value
            == {"closed_by_scan": False, "last_scan_missing": False},
        )
        res_hist = await db.execute(q_hist)
        histories = res_hist.scalars().all()
        assert len(histories) == 1

        # Verify finding.reopened event is emitted
        q_evt = select(WorkflowEvent).where(
            WorkflowEvent.event_type == "finding.reopened",
            WorkflowEvent.correlation_id == scan_id_3,
        )
        res_evt = await db.execute(q_evt)
        events = res_evt.scalars().all()
        assert len(events) == 1
