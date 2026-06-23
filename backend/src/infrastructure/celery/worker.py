import asyncio
import threading
import uuid
from datetime import datetime, timezone

from celery import Celery
from src.core.config import settings
from src.infrastructure.database.models import ScanRun, Workflow, WorkflowEvent
from src.infrastructure.database.session import AsyncSessionLocal

celery_app = Celery("aegisx_worker", broker=settings.REDIS_URL)


def run_async_task(coro):
    """Run an async function synchronously in a safe separate thread.

    This avoids event loop conflicts.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop:
        result = []
        exception = []

        def target():
            try:
                res = asyncio.run(coro)
                result.append(res)
            except Exception as e:
                exception.append(e)

        t = threading.Thread(target=target)
        t.start()
        t.join()

        if exception:
            raise exception[0]
        return result[0] if result else None
    else:
        return asyncio.run(coro)


async def _execute_workflow_async(
    workflow_id: uuid.UUID, scan_run_id: uuid.UUID, scope_id: uuid.UUID
):
    async with AsyncSessionLocal() as db:
        workflow = await db.get(Workflow, workflow_id)
        scan_run = await db.get(ScanRun, scan_run_id)

        if not workflow:
            if scan_run:
                scan_run.status = "failed"
                scan_run.end_ts = datetime.now(timezone.utc)
                await db.commit()
            return

        if not scan_run:
            return

        # Pre-execution validations: Scope exists, not deleted, ownership authorization
        from src.infrastructure.database.models import Scope

        scope = await db.get(Scope, scope_id)
        if not scope or scope.deleted_at is not None:
            error_msg = "Scope not found or deleted"
            scan_run.status = "failed"
            scan_run.end_ts = datetime.now(timezone.utc)
            fail_event = WorkflowEvent(
                workflow_id=workflow_id,
                event_type="workflow.failed",
                correlation_id=scan_run_id,
                payload={"error": error_msg, "step_index": -1},
                timestamp=datetime.now(timezone.utc),
            )
            db.add(fail_event)
            await db.commit()
            return

        if scope.owner_id != workflow.owner_id:
            error_msg = "Unauthorized: Scope ownership mismatch"
            scan_run.status = "failed"
            scan_run.end_ts = datetime.now(timezone.utc)
            fail_event = WorkflowEvent(
                workflow_id=workflow_id,
                event_type="workflow.failed",
                correlation_id=scan_run_id,
                payload={"error": error_msg, "step_index": -1},
                timestamp=datetime.now(timezone.utc),
            )
            db.add(fail_event)
            await db.commit()
            return

        # Check if already cancelled
        if scan_run.status == "cancelled":
            return

        # Transition ScanRun status to running
        scan_run.status = "running"
        scan_run.start_ts = datetime.now(timezone.utc)

        # Log workflow.started event
        start_event = WorkflowEvent(
            workflow_id=workflow_id,
            event_type="workflow.started",
            correlation_id=scan_run_id,
            payload={"scan_run_id": str(scan_run_id)},
            timestamp=datetime.now(timezone.utc),
        )
        db.add(start_event)
        await db.commit()

        steps = workflow.definition.get("steps", [])

        for index, step in enumerate(steps):
            # Check for cancellation before executing step
            await db.refresh(scan_run)
            if scan_run.status == "cancelled":
                cancel_event = WorkflowEvent(
                    workflow_id=workflow_id,
                    event_type="workflow.cancelled",
                    correlation_id=scan_run_id,
                    payload={
                        "scan_run_id": str(scan_run_id),
                        "last_completed_step_index": index - 1,
                    },
                    timestamp=datetime.now(timezone.utc),
                )
                db.add(cancel_event)
                await db.commit()
                return

            step_type = step.get("type", "unknown")

            # Log step.started event
            step_started_evt = WorkflowEvent(
                workflow_id=workflow_id,
                event_type="step.started",
                correlation_id=scan_run_id,
                payload={"step_index": index, "step_type": step_type},
                timestamp=datetime.now(timezone.utc),
            )
            db.add(step_started_evt)
            await db.commit()

            # Parse tools (support step.get("tool") or
            # step.get("config", {}).get("tools", []))
            tools = []
            if "tool" in step:
                tools = [step["tool"]]
            else:
                config = step.get("config", {}) or {}
                tools = config.get("tools", [])
                if isinstance(tools, str):
                    tools = [tools]

            if tools:
                for tool in tools:
                    # 1. Locate plugin by name
                    from sqlalchemy import select
                    from src.infrastructure.database.models import Plugin
                    from src.plugins.host import PluginHost

                    q = select(Plugin).where(
                        Plugin.name == tool, Plugin.deleted_at.is_(None)
                    )
                    res = await db.execute(q)
                    plugin = res.scalar_one_or_none()

                    # 2. Verify plugin exists
                    if not plugin:
                        error_msg = f"Plugin tool '{tool}' not found"
                        scan_run.status = "failed"
                        scan_run.end_ts = datetime.now(timezone.utc)
                        fail_event = WorkflowEvent(
                            workflow_id=workflow_id,
                            event_type="workflow.failed",
                            correlation_id=scan_run_id,
                            payload={"error": error_msg, "step_index": index},
                            timestamp=datetime.now(timezone.utc),
                        )
                        db.add(fail_event)
                        await db.commit()
                        return

                    # 3. Verify plugin is approved
                    if plugin.state != "approved":
                        error_msg = (
                            f"Plugin '{tool}' is in '{plugin.state}' state. "
                            "Must be approved to execute."
                        )
                        await PluginHost.log_event(
                            db,
                            plugin.id,
                            "plugin.failed",
                            correlation_id=scan_run_id,
                            workflow_id=workflow_id,
                            scan_run_id=scan_run_id,
                            payload={"error": error_msg},
                        )
                        scan_run.status = "failed"
                        scan_run.end_ts = datetime.now(timezone.utc)
                        fail_event = WorkflowEvent(
                            workflow_id=workflow_id,
                            event_type="workflow.failed",
                            correlation_id=scan_run_id,
                            payload={"error": error_msg, "step_index": index},
                            timestamp=datetime.now(timezone.utc),
                        )
                        db.add(fail_event)
                        await db.commit()
                        return

                    # 4. Verify capability matches step type
                    capabilities = plugin.manifest.get("capabilities", [])
                    if step_type not in capabilities:
                        error_msg = (
                            f"Capability mismatch: step type '{step_type}' "
                            f"not supported by plugin capabilities {capabilities}"
                        )
                        await PluginHost.log_event(
                            db,
                            plugin.id,
                            "plugin.failed",
                            correlation_id=scan_run_id,
                            workflow_id=workflow_id,
                            scan_run_id=scan_run_id,
                            payload={"error": error_msg},
                        )
                        scan_run.status = "failed"
                        scan_run.end_ts = datetime.now(timezone.utc)
                        fail_event = WorkflowEvent(
                            workflow_id=workflow_id,
                            event_type="workflow.failed",
                            correlation_id=scan_run_id,
                            payload={"error": error_msg, "step_index": index},
                            timestamp=datetime.now(timezone.utc),
                        )
                        db.add(fail_event)
                        await db.commit()
                        return

                    # 4.5. Pre-scan validation for vulnerability scans
                    if step_type == "vulnerability-scan":
                        from src.infrastructure.database.models import (
                            Asset,
                            AssetPort,
                            AssetService,
                        )

                        validation_error = None
                        if not scope or scope.deleted_at is not None:
                            validation_error = "Scope not found or deleted"
                        elif scope.owner_id != workflow.owner_id:
                            validation_error = "Unauthorized: Scope ownership mismatch"
                        else:
                            q_ast = select(Asset).where(
                                Asset.scope_id == scope_id,
                                Asset.deleted_at.is_(None),
                            )
                            res_ast = await db.execute(q_ast)
                            assets = res_ast.scalars().all()
                            if not assets:
                                validation_error = (
                                    "Asset validation failed: No assets found in scope"
                                )
                            else:
                                asset_ids = [a.id for a in assets]
                                q_ports = select(AssetPort).where(
                                    AssetPort.asset_id.in_(asset_ids)
                                )
                                res_ports = await db.execute(q_ports)
                                ports = res_ports.scalars().all()
                                if not ports:
                                    validation_error = (
                                        "Port validation failed: No ports "
                                        "found in scope"
                                    )
                                else:
                                    port_ids = [p.id for p in ports]
                                    q_svcs = select(AssetService).where(
                                        AssetService.asset_port_id.in_(port_ids)
                                    )
                                    res_svcs = await db.execute(q_svcs)
                                    services = res_svcs.scalars().all()
                                    if not services:
                                        validation_error = (
                                            "Service validation failed: "
                                            "No services found in scope"
                                        )

                        if validation_error:
                            await PluginHost.log_event(
                                db,
                                plugin.id,
                                "plugin.failed",
                                correlation_id=scan_run_id,
                                workflow_id=workflow_id,
                                scan_run_id=scan_run_id,
                                payload={"error": validation_error},
                            )
                            scan_run.status = "failed"
                            scan_run.end_ts = datetime.now(timezone.utc)
                            fail_event = WorkflowEvent(
                                workflow_id=workflow_id,
                                event_type="workflow.failed",
                                correlation_id=scan_run_id,
                                payload={
                                    "error": validation_error,
                                    "step_index": index,
                                },
                                timestamp=datetime.now(timezone.utc),
                            )
                            db.add(fail_event)
                            await db.commit()
                            return

                    # 5. Execute plugin through PluginHost
                    plugin_payload = {
                        "scope_id": str(scope_id),
                        "config": step.get("config", {}) or {},
                        "definition": scope.definition if scope else {},
                    }
                    try:
                        scan_run.plugin_id = plugin.id
                        await db.commit()

                        result = await PluginHost.run_plugin(
                            db=db,
                            plugin_id=plugin.id,
                            entry_point=plugin.manifest.get("entry_point"),
                            payload=plugin_payload,
                            timeout=plugin.manifest.get("timeout", 30),
                            correlation_id=scan_run_id,
                            workflow_id=workflow_id,
                            scan_run_id=scan_run_id,
                        )

                        # Normalize results and persist assets
                        if step_type == "discovery":
                            raw_out = result.get("raw_output", "")
                            from src.services.discovery_normalization_service import (
                                DiscoveryNormalizationService,
                            )

                            normalized_assets = DiscoveryNormalizationService.normalize(
                                plugin.name, raw_out
                            )

                            from src.services.asset_service import (
                                process_discovered_assets,
                            )

                            await process_discovered_assets(
                                db=db,
                                scope_id=scope_id,
                                assets_list=normalized_assets,
                                scan_run_id=scan_run_id,
                                workflow_id=workflow_id,
                                actor_id=workflow.owner_id,
                            )
                        elif step_type == "port-scan":
                            raw_out = result.get("raw_output", "")
                            from src.services.service_normalization_service import (
                                ServiceNormalizationService,
                            )

                            normalized_ports = (
                                ServiceNormalizationService.normalize_naabu(raw_out)
                            )

                            from src.services.port_service import PortService

                            await PortService.process_discovered_ports(
                                db=db,
                                scope_id=scope_id,
                                ports_list=normalized_ports,
                                scan_run_id=scan_run_id,
                                workflow_id=workflow_id,
                                actor_id=workflow.owner_id,
                            )
                        elif step_type == "service-enum":
                            raw_out = result.get("raw_output", "")
                            from src.services.service_normalization_service import (
                                ServiceNormalizationService,
                            )

                            normalized_services = (
                                ServiceNormalizationService.normalize_nmap(raw_out)
                            )

                            from src.services.service_service import ServiceService

                            await ServiceService.process_discovered_services(
                                db=db,
                                scope_id=scope_id,
                                services_list=normalized_services,
                                scan_run_id=scan_run_id,
                                workflow_id=workflow_id,
                                actor_id=workflow.owner_id,
                            )
                        elif step_type == "vulnerability-scan":
                            raw_out = result.get("raw_output", "")
                            from src.services.finding_normalization_service import (
                                FindingNormalizationService,
                            )

                            normalized_findings = (
                                FindingNormalizationService.normalize_nuclei(raw_out)
                            )

                            from src.services.finding_service import (
                                FindingService,
                            )

                            processed = (
                                await FindingService.process_discovered_findings(
                                    db=db,
                                    scope_id=scope_id,
                                    findings_list=normalized_findings,
                                    scan_run_id=scan_run_id,
                                    workflow_id=workflow_id,
                                    actor_id=workflow.owner_id,
                                )
                            )

                            from src.services.finding_reconciliation_service import (
                                FindingReconciliationService,
                            )

                            await FindingReconciliationService.reconcile_findings(
                                db=db,
                                scope_id=scope_id,
                                scan_run_id=scan_run_id,
                                workflow_id=workflow_id,
                                actor_id=workflow.owner_id,
                                source_plugin=plugin.name,
                                step_type=step_type,
                                step_config=step.get("config", {}) or {},
                                processed_fingerprints=processed,
                            )
                    except Exception as e:
                        error_msg = f"Plugin execution crashed: {str(e)}"
                        scan_run.status = "failed"
                        scan_run.end_ts = datetime.now(timezone.utc)
                        fail_event = WorkflowEvent(
                            workflow_id=workflow_id,
                            event_type="workflow.failed",
                            correlation_id=scan_run_id,
                            payload={"error": error_msg, "step_index": index},
                            timestamp=datetime.now(timezone.utc),
                        )
                        db.add(fail_event)
                        await db.commit()
                        return
            else:
                # Simulate step execution delay if no tool is attached
                await asyncio.sleep(0.01)

            # Automatically refresh snapshots after successful step completion
            if step_type in [
                "discovery",
                "port-scan",
                "service-enum",
                "vulnerability-scan",
            ]:
                try:
                    from sqlalchemy import select
                    from src.infrastructure.database.models import Asset
                    from src.services.asset_intelligence_service import (
                        AssetIntelligenceService,
                    )
                    from src.services.asset_risk_snapshot_service import (
                        AssetRiskSnapshotService,
                    )
                    from src.services.correlation_snapshot_service import (
                        CorrelationSnapshotService,
                    )
                    from src.services.dashboard_service import DashboardService
                    from src.services.executive_report_service import (
                        ExecutiveReportService,
                    )

                    q_assets = select(Asset).where(
                        Asset.scope_id == scope_id, Asset.deleted_at.is_(None)
                    )
                    res_assets = await db.execute(q_assets)
                    assets = res_assets.scalars().all()

                    for asset in assets:
                        try:
                            # 1. Update AssetIntelligenceService
                            await AssetIntelligenceService.update_asset_snapshot(
                                db, asset.id
                            )
                            # 2. Update CorrelationSnapshotService
                            await CorrelationSnapshotService.update_snapshot(
                                db,
                                asset.id,
                                scan_run_id=scan_run_id,
                                workflow_id=workflow_id,
                            )
                            # 3. Update AssetRiskSnapshotService
                            await AssetRiskSnapshotService.update_snapshot(
                                db,
                                asset.id,
                                scan_run_id=scan_run_id,
                                workflow_id=workflow_id,
                            )
                            # 3.5. Update RecommendationSnapshotService
                            from src.services.recommendation_snapshot_service import (
                                RecommendationSnapshotService,
                            )

                            await RecommendationSnapshotService.update_snapshot(
                                db, asset.id
                            )
                            # 4. Invalidate report and AI caches for asset
                            from src.services.report_cache_service import (
                                ReportCacheService,
                            )

                            ReportCacheService.invalidate_for_asset(asset.id)
                        except Exception as asset_err:
                            import logging

                            logging.error(
                                "Failed to update snapshots for asset "
                                f"{asset.id}: {asset_err}"
                            )

                    # 4. Refresh Dashboard and Executive report caches
                    try:
                        await DashboardService.refresh_cache(
                            db, scan_run_id=scan_run_id, workflow_id=workflow_id
                        )
                    except Exception as dash_err:
                        import logging

                        logging.error(
                            f"Failed to refresh DashboardService cache: {dash_err}"
                        )

                    try:
                        await ExecutiveReportService.refresh_cache(
                            db, scan_run_id=scan_run_id, workflow_id=workflow_id
                        )
                        from src.services.ai_cache_service import AICacheService

                        AICacheService.invalidate_for_asset("executive")
                    except Exception as exec_err:
                        import logging

                        logging.error(
                            "Failed to refresh ExecutiveReportService cache: "
                            f"{exec_err}"
                        )

                except Exception as scope_err:
                    import logging

                    logging.error(
                        "Failed to fetch assets for snapshot updates in "
                        f"scope {scope_id}: {scope_err}"
                    )

            # Log step.completed event
            step_completed_evt = WorkflowEvent(
                workflow_id=workflow_id,
                event_type="step.completed",
                correlation_id=scan_run_id,
                payload={"step_index": index, "step_type": step_type},
                timestamp=datetime.now(timezone.utc),
            )
            db.add(step_completed_evt)
            await db.commit()

        # Update ScanRun to completed
        await db.refresh(scan_run)
        if scan_run.status != "cancelled" and scan_run.status != "failed":
            scan_run.status = "completed"
            scan_run.end_ts = datetime.now(timezone.utc)

            completed_evt = WorkflowEvent(
                workflow_id=workflow_id,
                event_type="workflow.completed",
                correlation_id=scan_run_id,
                payload={"scan_run_id": str(scan_run_id)},
                timestamp=datetime.now(timezone.utc),
            )
            db.add(completed_evt)
            await db.commit()


@celery_app.task(name="execute_workflow_task")
def execute_workflow_task(
    workflow_id_str: str, scan_run_id_str: str, scope_id_str: str
):
    workflow_id = uuid.UUID(workflow_id_str)
    scan_run_id = uuid.UUID(scan_run_id_str)
    scope_id = uuid.UUID(scope_id_str)
    return run_async_task(_execute_workflow_async(workflow_id, scan_run_id, scope_id))
