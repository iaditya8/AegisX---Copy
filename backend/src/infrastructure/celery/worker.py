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
        # Cold start recovery check
        from src.services.unified_security_intelligence_fabric_service import UnifiedSecurityIntelligenceFabricService
        from src.services.cache_bootstrap_service import CacheBootstrapService

        if len(UnifiedSecurityIntelligenceFabricService.get_all_fabric_nodes()) == 0:
            import logging
            logging.info("Cold start detected. Bootstrapping cache recovery pipeline...")
            await CacheBootstrapService.bootstrap_cache(db, scope_id=scope_id)

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
                        "definition": scope.definition if scope is not None else {},
                    }
                    try:
                        scan_run.plugin_id = plugin.id
                        await db.commit()

                        result = await PluginHost.run_plugin(
                            db=db,
                            plugin_id=plugin.id,
                            entry_point=plugin.manifest.get("entry_point") or "",
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
                            # 3.6. Update RemediationSnapshotService
                            from src.services.remediation_snapshot_service import (
                                RemediationSnapshotService,
                            )

                            RemediationSnapshotService.update_snapshot(asset.id)
                            # 3.7. Update GovernanceSnapshotService and detect drift
                            from src.services.compliance_drift_service import (
                                ComplianceDriftService,
                            )
                            from src.services.governance_snapshot_service import (
                                GovernanceSnapshotService,
                            )

                            await GovernanceSnapshotService.update_snapshot(
                                db, asset.id
                            )
                            await ComplianceDriftService.detect_drift(db)
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

                    try:
                        from src.services.alert_escalation_service import (
                            AlertEscalationService,
                        )
                        from src.services.alert_generation_service import (
                            AlertGenerationService,
                        )
                        from src.services.continuous_refresh_service import (
                            ContinuousRefreshService,
                        )
                        from src.services.incident_escalation_service import (
                            IncidentEscalationService,
                        )
                        from src.services.incident_service import IncidentService
                        from src.services.case_service import CaseService

                        await ContinuousRefreshService.refresh_all(db)
                        await AlertGenerationService.generate_alerts(db)
                        await AlertEscalationService.process_escalations(db)
                        await IncidentService.sync_alerts(db)
                        await IncidentEscalationService.process_escalations(db)
                        try:
                            await CaseService.sync_cases(db)
                        except Exception as case_sync_err:
                            import logging
                            logging.error(f"Failed to sync cases: {case_sync_err}")

                        try:
                            from src.services.detection_gap_service import DetectionGapService
                            from src.services.detection_drift_service import DetectionDriftService
                            from src.services.detection_snapshot_service import DetectionSnapshotService

                            prev_snap = DetectionSnapshotService._snapshots.get(scope_id)
                            await DetectionGapService.check_gaps_and_regressions(db, scope_id=scope_id, prev_snapshot=prev_snap)
                            await DetectionDriftService.check_drift(db, scope_id=scope_id, prev_snapshot=prev_snap)
                            DetectionSnapshotService.generate_snapshot(scope_id)
                        except Exception as det_err:
                            import logging
                            logging.error(f"Failed to process detection coverage checks: {det_err}")

                        try:
                            from src.services.ioc_correlation_service import IOCCorrelationService
                            from src.services.ioc_drift_service import IOCDriftService
                            from src.services.threat_intelligence_snapshot_service import ThreatIntelligenceSnapshotService

                            await IOCCorrelationService.correlate_iocs(db)
                            prev_ti_snap = ThreatIntelligenceSnapshotService._snapshots.get(scope_id)
                            await IOCDriftService.check_drift(db, scope_id=scope_id, prev_snapshot=prev_ti_snap)
                            ThreatIntelligenceSnapshotService.generate_snapshot(scope_id)
                        except Exception as ti_err:
                            import logging
                            logging.error(f"Failed to process threat intelligence checks: {ti_err}")

                        try:
                            from src.services.ioc_hunt_service import IOCHuntService
                            from src.services.attack_hunt_service import AttackHuntService
                            from src.services.hunt_drift_service import HuntDriftService
                            from src.services.hunt_snapshot_service import HuntSnapshotService

                            await IOCHuntService.sync_ioc_hunts()
                            await AttackHuntService.sync_attack_hunts(db)

                            prev_hunt_snap = HuntSnapshotService._snapshots.get(scope_id)
                            await HuntDriftService.check_drift(db, scope_id=scope_id, prev_snapshot=prev_hunt_snap)
                            HuntSnapshotService.generate_snapshot(scope_id)
                        except Exception as hunt_err:
                            import logging
                            logging.error(f"Failed to process threat hunting checks: {hunt_err}")

                        try:
                            from src.services.attack_validation_service import AttackValidationService
                            from src.services.purple_team_drift_service import PurpleTeamDriftService
                            from src.services.purple_team_snapshot_service import PurpleTeamSnapshotService
                            from src.services.purple_team_service import PurpleTeamService
                            from src.domain.entities.purple_team import ExerciseStatus

                            exercises = PurpleTeamService.get_all_exercises()
                            if scope_id:
                                exercises = [e for e in exercises if e.scope_id == scope_id]

                            for ex in exercises:
                                if ex.status != ExerciseStatus.CLOSED:
                                    await AttackValidationService.validate_exercise_techniques(db, ex.exercise_id)

                            prev_pt_snap = PurpleTeamSnapshotService._snapshots.get(scope_id)
                            await PurpleTeamDriftService.check_drift(db, scope_id=scope_id, prev_snapshot=prev_pt_snap)
                            PurpleTeamSnapshotService.generate_snapshot(scope_id)
                        except Exception as pt_err:
                            import logging
                            logging.error(f"Failed to process purple team checks: {pt_err}")

                        try:
                            from src.services.exposure_service import ExposureService
                            from src.services.exposure_drift_service import ExposureDriftService
                            from src.services.exposure_snapshot_service import ExposureSnapshotService

                            await ExposureService.sync_exposures(db)

                            prev_exp_snap = ExposureSnapshotService._snapshots.get(scope_id)
                            await ExposureDriftService.check_drift(db, scope_id=scope_id, prev_snapshot=prev_exp_snap)
                            await ExposureSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as exp_err:
                            import logging
                            logging.error(f"Failed to process exposure management checks: {exp_err}")

                        try:
                            from src.services.security_posture_service import SecurityPostureService
                            from src.services.posture_drift_service import PostureDriftService
                            from src.services.security_posture_snapshot_service import SecurityPostureSnapshotService

                            await SecurityPostureService.sync_postures(db)

                            prev_posture_snap = SecurityPostureSnapshotService._snapshots.get(scope_id)
                            await PostureDriftService.check_drift(db, scope_id=scope_id, prev_snapshot=prev_posture_snap)
                            await SecurityPostureSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as posture_err:
                            import logging
                            logging.error(f"Failed to process security posture checks: {posture_err}")

                        try:
                            from src.services.control_validation_service import ControlValidationService
                            from src.services.control_drift_service import ControlDriftService
                            from src.services.control_validation_snapshot_service import ControlValidationSnapshotService

                            await ControlValidationService.sync_controls(db)

                            prev_control_snap = ControlValidationSnapshotService._snapshots.get(scope_id)
                            await ControlDriftService.check_drift(db, scope_id=scope_id, prev_snapshot=prev_control_snap)
                            await ControlValidationSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as control_err:
                            import logging
                            logging.error(f"Failed to process control validation checks: {control_err}")

                        try:
                            from src.services.security_program_service import SecurityProgramService
                            from src.services.program_drift_service import ProgramDriftService
                            from src.services.security_program_snapshot_service import SecurityProgramSnapshotService

                            await SecurityProgramService.sync_programs(db)

                            prev_program_snap = SecurityProgramSnapshotService._snapshots.get(scope_id)
                            await ProgramDriftService.check_drift(db, scope_id=scope_id, prev_snapshot=prev_program_snap)
                            await SecurityProgramSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as program_err:
                            import logging
                            logging.error(f"Failed to process security program checks: {program_err}")

                        try:
                            from src.services.executive_reporting_service import ExecutiveReportingService
                            from src.services.executive_trend_service import ExecutiveTrendService
                            from src.services.executive_drift_service import ExecutiveDriftService
                            from src.services.executive_snapshot_service import ExecutiveSnapshotService

                            await ExecutiveReportingService.sync_reports(db)
                            ExecutiveTrendService.calculate_trends(scope_id)

                            prev_exec_snap = ExecutiveSnapshotService._snapshots.get(scope_id)
                            await ExecutiveDriftService.check_drift(db, scope_id=scope_id, prev_snapshot=prev_exec_snap)
                            await ExecutiveSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as exec_err:
                            import logging
                            logging.error(f"Failed to process executive reporting checks: {exec_err}")

                        try:
                            from src.services.cyber_resilience_service import CyberResilienceService
                            from src.services.resilience_drift_service import ResilienceDriftService
                            from src.services.cyber_resilience_snapshot_service import CyberResilienceSnapshotService

                            await CyberResilienceService.sync_resilience(db)

                            prev_res_snap = CyberResilienceSnapshotService._snapshots.get(scope_id)
                            await ResilienceDriftService.check_drift(db, scope_id=scope_id, prev_snapshot=prev_res_snap)
                            await CyberResilienceSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as res_err:
                            import logging
                            logging.error(f"Failed to perform cyber resilience intelligence checks: {res_err}")

                        try:
                            from src.services.security_operations_analytics_service import SecurityOperationsAnalyticsService
                            from src.services.analyst_performance_service import AnalystPerformanceService
                            from src.services.operational_kpi_service import OperationalKPIService
                            from src.services.operational_kri_service import OperationalKRIService
                            from src.services.soc_drift_service import SOCDriftService
                            from src.services.soc_snapshot_service import SOCSnapshotService

                            await SecurityOperationsAnalyticsService.sync_analytics(db)
                            await AnalystPerformanceService.calculate()
                            await OperationalKPIService.calculate()
                            await OperationalKRIService.calculate()
                            
                            prev_soc_snap = SOCSnapshotService._snapshots.get(scope_id)
                            await SOCDriftService.process_drift(db, scope_id=scope_id, prev_snapshot=prev_soc_snap)
                            await SOCSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as soc_err:
                            import logging
                            logging.error(f"Failed to perform SOC analytics intelligence checks: {soc_err}")

                        try:
                            from src.services.cyber_risk_quantification_service import CyberRiskQuantificationService
                            from src.services.loss_expectancy_service import LossExpectancyService
                            from src.services.residual_risk_service import ResidualRiskService
                            from src.services.risk_forecast_service import RiskForecastService
                            from src.services.risk_trend_service import RiskTrendService
                            from src.services.risk_drift_service import RiskDriftService
                            from src.services.risk_quantification_snapshot_service import RiskQuantificationSnapshotService

                            # Sprint 30 Worker Execution Order
                            await CyberRiskQuantificationService.sync_risks(db)
                            LossExpectancyService.calculate()
                            ResidualRiskService.calculate()
                            RiskForecastService.calculate()
                            RiskTrendService.calculate()
                            
                            prev_risk_snap = RiskQuantificationSnapshotService._snapshots.get(scope_id)
                            await RiskDriftService.process_drift(db, scope_id=scope_id, prev_snapshot=prev_risk_snap)
                            await RiskQuantificationSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as risk_err:
                            import logging
                            logging.error(f"Failed to perform cyber risk quantification intelligence checks: {risk_err}")

                        try:
                            from src.services.governance_risk_compliance_service import GovernanceRiskComplianceService
                            from src.services.framework_mapping_service import FrameworkMappingService
                            from src.services.compliance_scoring_service import ComplianceScoringService
                            from src.services.audit_readiness_service import AuditReadinessService
                            from src.services.compliance_gap_service import ComplianceGapService
                            from src.services.grc_compliance_drift_service import GRCComplianceDriftService
                            from src.services.compliance_snapshot_service import ComplianceSnapshotService

                            # Sprint 31 GRC Worker Execution Order
                            await GovernanceRiskComplianceService.sync_assessments(db)
                            ComplianceScoringService.calculate()
                            ComplianceGapService.calculate()
                            GovernanceRiskComplianceService.recalculate_assessments()
                            
                            prev_grc_snap = ComplianceSnapshotService._snapshots.get(scope_id)
                            await GRCComplianceDriftService.process_drift(db, scope_id=scope_id, prev_snapshot=prev_grc_snap)
                            await ComplianceSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as grc_err:
                            import logging
                            logging.error(f"Failed to perform GRC intelligence checks: {grc_err}")

                        try:
                            from src.services.security_knowledge_service import SecurityKnowledgeService
                            from src.services.knowledge_relationship_service import KnowledgeRelationshipService
                            from src.services.knowledge_relevance_service import KnowledgeRelevanceService
                            from src.services.knowledge_recommendation_service import KnowledgeRecommendationService
                            from src.services.knowledge_drift_service import KnowledgeDriftService
                            from src.services.knowledge_snapshot_service import KnowledgeSnapshotService

                            # Sprint 32 GRC Knowledge Worker Execution Order
                            await SecurityKnowledgeService.sync_knowledge(db)
                            KnowledgeRelationshipService.calculate()
                            KnowledgeRelevanceService.calculate()
                            KnowledgeRecommendationService.calculate()
                            SecurityKnowledgeService.recalculate_knowledge()
                            
                            prev_know_snap = KnowledgeSnapshotService._snapshots.get(scope_id)
                            await KnowledgeDriftService.process_drift(db, scope_id=scope_id, prev_snapshot=prev_know_snap)
                            await KnowledgeSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as know_err:
                            import logging
                            logging.error(f"Failed to perform GRC knowledge base intelligence checks: {know_err}")

                        try:
                            from src.services.threat_intelligence_service import ThreatIntelligenceService
                            from src.services.threat_intel_fusion_service import ThreatIntelFusionService
                            from src.services.threat_intel_drift_service import ThreatIntelDriftService
                            from src.services.threat_intel_snapshot_service import ThreatIntelSnapshotService
                            from src.domain.entities.threat_intel import ThreatIntelStatus

                            # Sprint 33 GRC Threat Intel Worker Execution Order
                            await ThreatIntelligenceService.sync_threats(db)
                            
                            # Run fusion score calculations and persist FUSED status (Finding 2)
                            for threat in ThreatIntelligenceService.get_all_threats():
                                if threat.status == ThreatIntelStatus.ARCHIVED:
                                    continue
                                score = ThreatIntelFusionService.calculate_fusion_score(threat.value, threat.indicator_type.value)
                                await ThreatIntelligenceService.fuse_threat(threat.threat_intel_id, score)

                            ThreatIntelFusionService.calculate()

                            prev_threat_snap = ThreatIntelSnapshotService._snapshots.get(scope_id)
                            await ThreatIntelDriftService.process_drift(db, scope_id=scope_id, prev_snapshot=prev_threat_snap)
                            await ThreatIntelSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as threat_err:
                            import logging
                            logging.error(f"Failed to perform GRC threat intelligence checks: {threat_err}")

                        try:
                            # Sprint 34: Unified Security Intelligence Graph
                            from src.services.security_intelligence_graph_service import SecurityIntelligenceGraphService
                            from src.services.graph_correlation_service import GraphCorrelationService
                            from src.services.graph_drift_service import GraphDriftService
                            from src.services.graph_snapshot_service import GraphSnapshotService

                            await SecurityIntelligenceGraphService.rebuild_graph_topology(db)
                            await GraphCorrelationService.recalculate_cross_domain_links()

                            prev_graph_snap = GraphSnapshotService._snapshots.get(scope_id)
                            await GraphDriftService.process_drift(db, scope_id=scope_id, prev_snapshot=prev_graph_snap)
                            await GraphSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as graph_err:
                            import logging
                            logging.error(f"Failed to perform GRC graph checks: {graph_err}")

                        try:
                            # Sprint 35: Security Decision Intelligence
                            from src.services.security_decision_service import SecurityDecisionService
                            from src.services.decision_tradeoff_service import DecisionTradeoffService
                            from src.services.decision_drift_service import DecisionDriftService
                            from src.services.decision_snapshot_service import DecisionSnapshotService

                            await SecurityDecisionService.sync_decision_recommendations(db)
                            DecisionTradeoffService.calculate()
                            
                            prev_dec_snap = DecisionSnapshotService._snapshots.get(scope_id)
                            await DecisionDriftService.process_drift(db, scope_id=scope_id, prev_snapshot=prev_dec_snap)
                            await DecisionSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as decision_err:
                            import logging
                            logging.error(f"Failed to perform GRC decision checks: {decision_err}")

                        try:
                            # Sprint 36: Autonomous Security Planning
                            from src.services.autonomous_security_planning_service import AutonomousSecurityPlanningService
                            from src.services.planning_optimization_service import PlanningOptimizationService
                            from src.services.planning_drift_service import PlanningDriftService
                            from src.services.planning_snapshot_service import PlanningSnapshotService

                            await AutonomousSecurityPlanningService.sync_plans(db)
                            PlanningOptimizationService.optimize_sequences()
                            
                            prev_plan_snap = PlanningSnapshotService._snapshots.get(scope_id)
                            await PlanningDriftService.process_drift(db, scope_id=scope_id, prev_snapshot=prev_plan_snap)
                            await PlanningSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as planning_err:
                            import logging
                            logging.error(f"Failed to perform GRC planning checks: {planning_err}")

                        try:
                            # Sprint 37: Unified Security Intelligence Fabric
                            from src.services.unified_security_intelligence_fabric_service import UnifiedSecurityIntelligenceFabricService
                            from src.services.intelligence_propagation_service import IntelligencePropagationService
                            from src.services.fabric_drift_service import FabricDriftService
                            from src.services.fabric_snapshot_service import FabricSnapshotService

                            await UnifiedSecurityIntelligenceFabricService.sync_fabric_state(db)
                            IntelligencePropagationService.process_propagation()
                            
                            prev_fabric_snap = FabricSnapshotService._snapshots.get(scope_id)
                            await FabricDriftService.process_drift(db, scope_id=scope_id, prev_snapshot=prev_fabric_snap)
                            await FabricSnapshotService.generate_snapshot(db, scope_id)
                        except Exception as fabric_err:
                            import logging
                            logging.error(f"Failed to perform GRC fabric checks: {fabric_err}")

                    except Exception as refresh_err:
                        import logging

                        logging.error(
                            "Failed to run ContinuousRefreshService.refresh_all: "
                            f"{refresh_err}"
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
