import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Finding, FindingEvidence
from src.services.asset_report_service import AssetReportService
from src.services.dashboard_trend_service import DashboardTrendService
from src.services.executive_report_service import ExecutiveReportService

CONTEXT_VERSION = "1.0"


class AIContextBuilder:
    @classmethod
    async def _build_governance_data(
        cls, db: AsyncSession, asset_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Aggregate governance statistics and status for an asset."""
        from src.services.compliance_mapping_service import ComplianceMappingService
        from src.services.governance_service import GovernanceService
        from src.services.remediation_service import RemediationService
        from src.services.risk_acceptance_service import (
            RiskAcceptanceService,
            RiskAcceptanceStatus,
        )

        gov_status = await GovernanceService.evaluate_asset_governance(db, asset_id)
        asset_acceptances = RiskAcceptanceService.get_acceptances_by_asset(asset_id)

        active_acc = [
            a.recommendation_fingerprint
            for a in asset_acceptances
            if a.status in [RiskAcceptanceStatus.ACTIVE, RiskAcceptanceStatus.EXPIRING]
        ]
        expired_acc = [
            a.recommendation_fingerprint
            for a in asset_acceptances
            if a.status == RiskAcceptanceStatus.EXPIRED
        ]

        controls = await ComplianceMappingService.get_compliance_controls(db)
        failed_controls = [
            c.control_id for c in controls if asset_id in c.affected_assets
        ]

        remediations = RemediationService.get_remediations_by_asset(asset_id)
        now = datetime.now(timezone.utc)
        sla_breaches = [
            str(r.remediation_id)
            for r in remediations
            if r.status.value in ["OPEN", "IN_PROGRESS", "DEFERRED"]
            and r.due_date < now
        ]

        return {
            "governance_status": gov_status.value,
            "accepted_risks": active_acc,
            "expired_acceptances": expired_acc,
            "compliance_controls": failed_controls,
            "sla_breaches": sla_breaches,
        }

    @classmethod
    async def _build_monitoring_data(
        cls, db: AsyncSession, asset_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate continuous monitoring events and drift statistics."""
        from src.services.continuous_refresh_service import ContinuousRefreshService

        events = ContinuousRefreshService.get_all_events()

        if asset_id:
            asset_events = [e for e in events if e.asset_id == asset_id]
        else:
            asset_events = events

        monitoring_events = [
            {
                "event_id": str(e.event_id),
                "change_type": e.change_type,
                "asset_id": str(e.asset_id),
                "finding_id": str(e.finding_id) if e.finding_id else None,
                "previous_state": e.previous_state,
                "current_state": e.current_state,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in asset_events
        ]

        asset_drift = [
            m
            for m in monitoring_events
            if m["change_type"] in ["ASSET_ADDED", "ASSET_MODIFIED", "ASSET_REMOVED"]
        ]
        finding_drift = [
            m
            for m in monitoring_events
            if m["change_type"]
            in [
                "FINDING_ADDED",
                "FINDING_RESOLVED",
                "FINDING_REDISCOVERED",
                "FINDING_MODIFIED",
            ]
        ]
        risk_drift = [
            m
            for m in monitoring_events
            if m["change_type"] in ["RISK_INCREASED", "RISK_DECREASED", "RISK_DRIFT"]
        ]
        governance_drift = [
            m
            for m in monitoring_events
            if m["change_type"]
            in [
                "COMPLIANCE_FAILED",
                "COMPLIANCE_RESTORED",
                "RISK_ACCEPTANCE_EXPIRED",
                "GOVERNANCE_DRIFT",
            ]
        ]

        return {
            "monitoring_events": monitoring_events,
            "asset_drift": asset_drift,
            "finding_drift": finding_drift,
            "risk_drift": risk_drift,
            "governance_drift": governance_drift,
        }

    @classmethod
    async def _build_alert_data(
        cls, db: AsyncSession, asset_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate alert details, workloads, and summary statistics."""
        from src.domain.entities.alert import AlertSeverity, AlertStatus
        from src.services.alert_lifecycle_service import AlertLifecycleService
        from src.services.alert_queue_service import AlertQueueService

        alerts = AlertLifecycleService.get_all_alerts()
        if asset_id:
            asset_alerts = [a for a in alerts if a.asset_id == asset_id]
        else:
            asset_alerts = alerts

        active_statuses = [
            AlertStatus.OPEN,
            AlertStatus.ACKNOWLEDGED,
            AlertStatus.IN_PROGRESS,
            AlertStatus.ESCALATED,
        ]

        active_alerts_list = [
            {
                "alert_id": str(a.alert_id),
                "alert_fingerprint": a.alert_fingerprint,
                "alert_type": a.alert_type.value,
                "severity": a.severity.value,
                "status": a.status.value,
                "asset_id": str(a.asset_id) if a.asset_id else None,
                "finding_id": str(a.finding_id) if a.finding_id else None,
                "title": a.title,
                "description": a.description,
                "owner": str(a.owner) if a.owner else None,
                "created_at": a.created_at.isoformat(),
                "updated_at": a.updated_at.isoformat(),
            }
            for a in asset_alerts
            if a.status in active_statuses
        ]

        critical_count = sum(
            1
            for a in asset_alerts
            if a.severity == AlertSeverity.CRITICAL and a.status in active_statuses
        )
        escalated_count = sum(
            1 for a in asset_alerts if a.status == AlertStatus.ESCALATED
        )
        owned_count = sum(
            1
            for a in asset_alerts
            if a.owner is not None and a.status in active_statuses
        )

        queue_stats = AlertQueueService.get_queue_stats()

        alert_summary = {
            "total_active_alerts": len(active_alerts_list),
            "critical_active_alerts": critical_count,
            "escalated_active_alerts": escalated_count,
            "owned_active_alerts": owned_count,
            "queue_stats": queue_stats,
        }

        return {
            "alert_summary": alert_summary,
            "active_alerts": active_alerts_list,
            "critical_alerts": critical_count,
            "escalated_alerts": escalated_count,
            "owned_alerts": owned_count,
        }

    @classmethod
    async def _build_incident_data(
        cls, db: AsyncSession, asset_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate incident summaries, active lists, timelines, and linked evidence."""
        from src.services.incident_evidence_service import IncidentEvidenceService
        from src.services.incident_history_service import IncidentHistoryService
        from src.services.incident_service import IncidentService
        from src.services.incident_snapshot_service import IncidentSnapshotService

        incidents = IncidentService.get_all_incidents()
        if asset_id:
            asset_incidents = [inc for inc in incidents if asset_id in inc.asset_ids]
        else:
            asset_incidents = incidents

        active_incidents_list = []
        for inc in asset_incidents:
            timeline = [
                {
                    "timestamp": h.timestamp.isoformat(),
                    "event_type": h.event_type,
                    "details": h.details,
                }
                for h in IncidentHistoryService.get_history(inc.incident_id)
            ]
            evidence = IncidentEvidenceService.get_evidence(inc.incident_id)

            active_incidents_list.append(
                {
                    "incident_id": str(inc.incident_id),
                    "incident_fingerprint": inc.incident_fingerprint,
                    "title": inc.title,
                    "description": inc.description,
                    "severity": (
                        inc.severity.value
                        if hasattr(inc.severity, "value")
                        else str(inc.severity)
                    ),
                    "status": (
                        inc.status.value
                        if hasattr(inc.status, "value")
                        else str(inc.status)
                    ),
                    "owner": str(inc.owner) if inc.owner else None,
                    "created_at": inc.created_at.isoformat(),
                    "updated_at": inc.updated_at.isoformat(),
                    "alert_ids": [str(aid) for aid in inc.alert_ids],
                    "asset_ids": [str(asid) for asid in inc.asset_ids],
                    "finding_ids": [str(fid) for fid in inc.finding_ids],
                    "recommendation_ids": inc.recommendation_ids,
                    "remediation_ids": [str(rid) for rid in inc.remediation_ids],
                    "incident_timeline": timeline,
                    "linked_evidence": evidence,
                }
            )

        snapshot = IncidentSnapshotService.get_snapshot()

        return {
            "incident_summary": snapshot,
            "active_incidents": active_incidents_list,
        }

    @classmethod
    async def build_incident_context(
        cls, db: AsyncSession, incident_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Aggregate context for a specific incident."""
        from src.services.incident_evidence_service import IncidentEvidenceService
        from src.services.incident_history_service import IncidentHistoryService
        from src.services.incident_service import IncidentService

        incident = IncidentService.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        timeline = [
            {
                "timestamp": h.timestamp.isoformat(),
                "event_type": h.event_type,
                "details": h.details,
            }
            for h in IncidentHistoryService.get_history(incident_id)
        ]
        evidence = IncidentEvidenceService.get_evidence(incident_id)

        asset_context = {}
        scope_id = None
        if incident.asset_ids:
            primary_asset_id = incident.asset_ids[0]
            try:
                asset_context = await cls.build_asset_context(db, primary_asset_id)
                from src.infrastructure.database.models import Asset
                asset_obj = await db.get(Asset, primary_asset_id)
                scope_id = asset_obj.scope_id if asset_obj else None
            except Exception:
                pass

        th_data = await cls._build_threat_hunting_data(scope_id)
        pt_data = await cls._build_purple_team_data(scope_id)
        exposure_data = await cls._build_exposure_data(scope_id)
        posture_data = await cls._build_security_posture_context_block(scope_id)
        control_data = await cls._build_control_validation_context_block(scope_id)
        program_data = await cls._build_security_program_context_block(scope_id)
        exec_data = await cls._build_executive_reporting_context_block(scope_id)

        return {
            "context_version": CONTEXT_VERSION,
            "incident_id": str(incident.incident_id),
            "incident_fingerprint": incident.incident_fingerprint,
            "title": incident.title,
            "description": incident.description,
            "severity": (
                incident.severity.value
                if hasattr(incident.severity, "value")
                else str(incident.severity)
            ),
            "status": (
                incident.status.value
                if hasattr(incident.status, "value")
                else str(incident.status)
            ),
            "owner": str(incident.owner) if incident.owner else None,
            "created_at": incident.created_at.isoformat(),
            "updated_at": incident.updated_at.isoformat(),
            "alert_ids": [str(aid) for aid in incident.alert_ids],
            "asset_ids": [str(asid) for asid in incident.asset_ids],
            "finding_ids": [str(fid) for fid in incident.finding_ids],
            "recommendation_ids": incident.recommendation_ids,
            "remediation_ids": [str(rid) for rid in incident.remediation_ids],
            "incident_timeline": timeline,
            "linked_evidence": evidence,
            "asset_context": asset_context,
            **th_data,
            **pt_data,
            **exposure_data,
            **posture_data,
            **control_data,
            **program_data,
            **exec_data,
        }

    @classmethod
    async def _build_threat_intelligence_data(
        cls, scope_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate threat intelligence summary, threat actors, campaigns, and active correlations."""
        if scope_id and isinstance(scope_id, str):
            try:
                scope_id = uuid.UUID(scope_id)
            except ValueError:
                pass

        from src.services.threat_intelligence_snapshot_service import ThreatIntelligenceSnapshotService
        from src.services.threat_actor_service import ThreatActorService
        from src.services.campaign_service import CampaignService
        from src.services.ioc_correlation_service import IOCCorrelationService

        snapshot = ThreatIntelligenceSnapshotService.get_snapshot(scope_id)
        actors = ThreatActorService.get_all_actors(scope_id)
        campaigns = CampaignService.get_all_campaigns(scope_id)
        correlations = IOCCorrelationService.get_all_correlations(scope_id)

        correlations_list = [
            {
                "correlation_id": str(c.correlation_id),
                "ioc_id": str(c.ioc_id),
                "ioc_fingerprint": c.ioc_fingerprint,
                "entity_type": c.entity_type,
                "entity_id": str(c.entity_id),
                "scope_id": str(c.scope_id) if c.scope_id else None,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in correlations
        ]

        return {
            "threat_intelligence_summary": snapshot["summary"],
            "threat_actors": [a.model_dump() for a in actors],
            "campaigns": [c.model_dump() for c in campaigns],
            "active_correlations": correlations_list,
        }

    @classmethod
    async def _build_threat_hunting_data(
        cls, scope_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate threat hunting summary, active hunts, and coverage statistics."""
        if scope_id and isinstance(scope_id, str):
            try:
                scope_id = uuid.UUID(scope_id)
            except ValueError:
                pass

        from src.services.hunt_snapshot_service import HuntSnapshotService
        from src.services.hunt_service import HuntService

        snapshot = HuntSnapshotService.get_snapshot(scope_id)
        hunts = HuntService.get_all_hunts()
        if scope_id:
            hunts = [h for h in hunts if h.scope_id == scope_id]

        active_hunts_list = [
            HuntService.to_response(h).model_dump()
            for h in hunts
            if h.status.value in ["OPEN", "ACTIVE", "UNDER_REVIEW", "ESCALATED"]
        ]

        for h in active_hunts_list:
            h["hunt_id"] = str(h["hunt_id"])
            h["owner_id"] = str(h["owner_id"]) if h["owner_id"] else None
            h["scope_id"] = str(h["scope_id"]) if h["scope_id"] else None
            for hyp in h.get("hypotheses", []):
                hyp["hypothesis_id"] = str(hyp["hypothesis_id"])
                hyp["hunt_id"] = str(hyp["hunt_id"])
            for f in h.get("findings", []):
                f["finding_id"] = str(f["finding_id"])
                f["hunt_id"] = str(f["hunt_id"])
                f["entity_id"] = str(f["entity_id"])

        return {
            "threat_hunting_summary": snapshot["summary"],
            "hunt_coverage": snapshot["coverage"],
            "active_hunts": active_hunts_list,
        }

    @classmethod
    async def _build_purple_team_data(
        cls, scope_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate Purple Team summary, active exercises, and validation statistics."""
        if scope_id and isinstance(scope_id, str):
            try:
                scope_id = uuid.UUID(scope_id)
            except ValueError:
                pass

        from src.services.purple_team_snapshot_service import PurpleTeamSnapshotService
        from src.services.purple_team_service import PurpleTeamService
        from src.services.purple_team_finding_service import PurpleTeamFindingService
        from src.services.attack_validation_service import AttackValidationService

        snapshot = PurpleTeamSnapshotService.get_snapshot(scope_id)
        exercises = PurpleTeamService.get_all_exercises()
        if scope_id:
            exercises = [e for e in exercises if e.scope_id == scope_id]

        active_exercises_list = [
            PurpleTeamService.to_response(e).model_dump()
            for e in exercises
            if e.status.value in ["OPEN", "ACTIVE", "UNDER_REVIEW", "COMPLETED"]
        ]

        for ex in active_exercises_list:
            ex_id_raw = ex["exercise_id"]
            ex["exercise_id"] = str(ex_id_raw)
            ex["scope_id"] = str(ex["scope_id"]) if ex["scope_id"] else None
            ex_id = uuid.UUID(ex_id_raw) if isinstance(ex_id_raw, str) else ex_id_raw
            ex["findings"] = [f.model_dump() for f in PurpleTeamFindingService.get_findings(ex_id)]
            ex["validations"] = [
                {
                    "validation_id": str(v.validation_id),
                    "technique_id": v.technique_id,
                    "validation_status": v.validation_status.value,
                    "expected_detection": v.expected_detection,
                    "actual_detection": v.actual_detection,
                    "coverage_gap": v.coverage_gap,
                }
                for v in AttackValidationService.get_exercise_validations(ex_id)
            ]

        for item in active_exercises_list:
            for f in item.get("findings", []):
                f["finding_id"] = str(f["finding_id"])
                f["exercise_id"] = str(f["exercise_id"])

        return {
            "purple_team_summary": snapshot["summary"],
            "purple_team_coverage": snapshot["coverage"],
            "active_exercises": active_exercises_list,
        }

    @classmethod
    async def build_asset_context(
        cls, db: AsyncSession, asset_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Aggregate context for a specific asset."""
        report = await AssetReportService.generate_asset_report(db, asset_id)
        if not report:
            raise ValueError(f"Asset {asset_id} not found or deleted")

        from src.services.recommendation_service import RecommendationService
        from src.services.recommendation_snapshot_service import (
            RecommendationSnapshotService,
        )
        from src.services.remediation_snapshot_service import (
            RemediationSnapshotService,
        )

        recs = await RecommendationService.generate_asset_recommendations(db, asset_id)
        rec_snapshot = RecommendationSnapshotService.get_snapshot(asset_id)
        rem_snapshot = RemediationSnapshotService.get_snapshot(asset_id)
        gov_data = await cls._build_governance_data(db, asset_id)
        monitoring_data = await cls._build_monitoring_data(db, asset_id)
        alert_data = await cls._build_alert_data(db, asset_id)
        incident_data = await cls._build_incident_data(db, asset_id)
        case_data = await cls._build_case_data(db, asset_id)
        detection_data = await cls._build_detection_data()

        scope_id = report["asset"].get("scope_id") if isinstance(report.get("asset"), dict) else None
        if not scope_id:
            from src.infrastructure.database.models import Asset
            asset_obj = await db.get(Asset, asset_id)
            scope_id = asset_obj.scope_id if asset_obj else None

        ti_data = await cls._build_threat_intelligence_data(scope_id)
        th_data = await cls._build_threat_hunting_data(scope_id)
        pt_data = await cls._build_purple_team_data(scope_id)
        exposure_data = await cls._build_exposure_data(scope_id)
        posture_data = await cls._build_security_posture_context_block(scope_id)
        control_data = await cls._build_control_validation_context_block(scope_id)
        program_data = await cls._build_security_program_context_block(scope_id)
        exec_data = await cls._build_executive_reporting_context_block(scope_id)

        return {
            "context_version": CONTEXT_VERSION,
            "asset": {
                **report["asset"],
                "ports": report.get("ports", []),
                "services": report.get("services", []),
                "technologies": report.get("technologies", []),
                "recommendation_snapshot": rec_snapshot,
                "remediation_snapshot": rem_snapshot,
                **gov_data,
                **monitoring_data,
                "alert_summary": alert_data["alert_summary"],
                "active_alerts": alert_data["active_alerts"],
                "critical_alerts": alert_data["critical_alerts"],
                "escalated_alerts": alert_data["escalated_alerts"],
                "owned_alerts": alert_data["owned_alerts"],
                "incident_summary": incident_data["incident_summary"],
                "active_incidents": incident_data["active_incidents"],
                "case_summary": case_data["case_summary"],
                "active_cases": case_data["active_cases"],
                "threat_intelligence_summary": ti_data["threat_intelligence_summary"],
                "threat_actors": ti_data["threat_actors"],
                "campaigns": ti_data["campaigns"],
                "active_correlations": ti_data["active_correlations"],
                "threat_hunting_summary": th_data["threat_hunting_summary"],
                "hunt_coverage": th_data["hunt_coverage"],
                "active_hunts": th_data["active_hunts"],
                "purple_team_summary": pt_data["purple_team_summary"],
                "purple_team_coverage": pt_data["purple_team_coverage"],
                "active_exercises": pt_data["active_exercises"],
                "exposure_summary": exposure_data["exposure_summary"],
                "active_exposures": exposure_data["active_exposures"],
                "attack_surface_inventory": exposure_data["attack_surface_inventory"],
                **posture_data,
                **control_data,
                **program_data,
                **exec_data,
            },
            "governance": gov_data,
            **monitoring_data,
            **alert_data,
            **incident_data,
            **case_data,
            **detection_data,
            **ti_data,
            **th_data,
            **pt_data,
            **exposure_data,
            **posture_data,
            **control_data,
            **program_data,
            **exec_data,
            "risk": report["risk"],
            "findings": report["findings"],
            "correlation": report["exposure"],
            "recommendations": [r.model_dump() for r in recs],
        }

    @classmethod
    async def build_finding_context(
        cls, db: AsyncSession, finding_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Aggregate context for a specific finding.

        Includes its asset and evidence details.
        """
        finding = await db.get(Finding, finding_id)
        if not finding:
            raise ValueError(f"Finding {finding_id} not found")

        # Fetch finding evidence
        q_evidence = select(FindingEvidence).where(
            FindingEvidence.finding_id == finding_id
        )
        res_evidence = await db.execute(q_evidence)
        evidence_list = res_evidence.scalars().all()

        evidence_data = [
            {
                "id": str(ev.id),
                "evidence_type": ev.evidence_type,
                "raw_request": ev.raw_request,
                "raw_response": ev.raw_response,
                "matched_at": ev.matched_at,
                "matcher_name": ev.matcher_name,
                "matcher_value": ev.matcher_value,
                "metadata_json": ev.metadata_json,
            }
            for ev in evidence_list
        ]

        from src.services.recommendation_service import RecommendationService
        from src.services.recommendation_snapshot_service import (
            RecommendationSnapshotService,
        )
        from src.services.remediation_service import RemediationService
        from src.services.remediation_snapshot_service import (
            RemediationSnapshotService,
        )

        recs = await RecommendationService.generate_finding_recommendations(
            db, finding_id
        )
        rec_snapshot = RecommendationSnapshotService.get_snapshot(finding.asset_id)
        rem_snapshot = RemediationSnapshotService.get_snapshot(finding.asset_id)
        gov_data = await cls._build_governance_data(db, finding.asset_id)
        monitoring_data = await cls._build_monitoring_data(db, finding.asset_id)
        alert_data = await cls._build_alert_data(db, finding.asset_id)
        incident_data = await cls._build_incident_data(db, finding.asset_id)
        case_data = await cls._build_case_data(db, finding.asset_id)

        finding_rems = [
            r
            for r in RemediationService.get_all_remediations()
            if r.finding_id == finding_id
        ]
        remediation_status = finding_rems[0].status.value if finding_rems else None
        remediation_owner = finding_rems[0].owner if finding_rems else None

        finding_dict = {
            "id": str(finding.id),
            "asset_id": str(finding.asset_id),
            "title": finding.title,
            "description": finding.description,
            "severity": finding.severity,
            "status": finding.status,
            "template_id": finding.template_id,
            "template_name": finding.template_name,
            "source_plugin": finding.source_plugin,
            "first_seen": (
                finding.first_seen.isoformat() if finding.first_seen else None
            ),
            "last_seen": finding.last_seen.isoformat() if finding.last_seen else None,
            "metadata_json": finding.metadata_json,
            "evidence": evidence_data,
            "remediation_status": remediation_status,
            "remediation_owner": remediation_owner,
        }

        # Fetch asset report for contextual asset details
        report = await AssetReportService.generate_asset_report(db, finding.asset_id)
        if not report:
            raise ValueError(
                f"Asset {finding.asset_id} associated with finding "
                f"{finding_id} not found"
            )

        scope_id = report["asset"].get("scope_id") if isinstance(report.get("asset"), dict) else None
        if not scope_id:
            from src.infrastructure.database.models import Asset
            asset_obj = await db.get(Asset, finding.asset_id)
            scope_id = asset_obj.scope_id if asset_obj else None

        th_data = await cls._build_threat_hunting_data(scope_id)
        pt_data = await cls._build_purple_team_data(scope_id)
        exposure_data = await cls._build_exposure_data(scope_id)
        posture_data = await cls._build_security_posture_context_block(scope_id)
        control_data = await cls._build_control_validation_context_block(scope_id)
        program_data = await cls._build_security_program_context_block(scope_id)
        exec_data = await cls._build_executive_reporting_context_block(scope_id)

        return {
            "context_version": CONTEXT_VERSION,
            "asset": {
                **report["asset"],
                "ports": report.get("ports", []),
                "services": report.get("services", []),
                "technologies": report.get("technologies", []),
                "recommendation_snapshot": rec_snapshot,
                "remediation_snapshot": rem_snapshot,
                "incident_summary": incident_data["incident_summary"],
                "active_incidents": incident_data["active_incidents"],
                "case_summary": case_data["case_summary"],
                "active_cases": case_data["active_cases"],
                "threat_hunting_summary": th_data["threat_hunting_summary"],
                "hunt_coverage": th_data["hunt_coverage"],
                "active_hunts": th_data["active_hunts"],
                "purple_team_summary": pt_data["purple_team_summary"],
                "purple_team_coverage": pt_data["purple_team_coverage"],
                "active_exercises": pt_data["active_exercises"],
                "exposure_summary": exposure_data["exposure_summary"],
                "active_exposures": exposure_data["active_exposures"],
                "attack_surface_inventory": exposure_data["attack_surface_inventory"],
                **posture_data,
                **control_data,
                **program_data,
                **exec_data,
            },
            "governance": gov_data,
            **monitoring_data,
            **alert_data,
            **incident_data,
            **case_data,
            **th_data,
            **pt_data,
            **exposure_data,
            **posture_data,
            **control_data,
            **program_data,
            **exec_data,
            "risk": report["risk"],
            "findings": [finding_dict],
            "correlation": report["exposure"],
            "recommendations": [r.model_dump() for r in recs],
        }

    @classmethod
    async def build_executive_context(cls, db: AsyncSession) -> Dict[str, Any]:
        """Aggregate organization-wide security posture and trend context."""
        report = await ExecutiveReportService.get_executive_report(db)
        trends = await DashboardTrendService.generate_trends(db, days=30)

        from src.services.governance_snapshot_service import GovernanceSnapshotService
        from src.services.prioritization_service import PrioritizationService

        top_assets = await PrioritizationService.get_top_assets(db, limit=10)
        top_findings = await PrioritizationService.get_top_findings(db, limit=20)
        top_technologies = await PrioritizationService.get_top_technologies(
            db, limit=20
        )
        top_products = await PrioritizationService.get_top_products(db, limit=20)
        gov_snapshot = await GovernanceSnapshotService.get_snapshot(db)
        monitoring_data = await cls._build_monitoring_data(db, asset_id=None)
        alert_data = await cls._build_alert_data(db, asset_id=None)
        incident_data = await cls._build_incident_data(db, asset_id=None)
        case_data = await cls._build_case_data(db, asset_id=None)
        detection_data = await cls._build_detection_data()
        ti_data = await cls._build_threat_intelligence_data(scope_id=None)
        th_data = await cls._build_threat_hunting_data(scope_id=None)
        pt_data = await cls._build_purple_team_data(scope_id=None)
        exposure_data = await cls._build_exposure_data(scope_id=None)
        posture_data = await cls._build_global_security_posture_context_block()
        control_data = await cls._build_global_control_validation_context_block()
        program_data = await cls._build_global_security_program_context_block()
        exec_data = await cls._build_global_executive_reporting_context_block()
        resilience_data = await cls._build_global_cyber_resilience_context_block()
        soc_data = await cls._build_global_soc_context_block()
        risk_quantification_data = await cls._build_global_risk_quantification_context_block()

        return {
            "context_version": CONTEXT_VERSION,
            "asset": {},
            "governance": gov_snapshot,
            **monitoring_data,
            **alert_data,
            **incident_data,
            **case_data,
            **detection_data,
            **ti_data,
            **th_data,
            **pt_data,
            **exposure_data,
            **posture_data,
            **control_data,
            **program_data,
            **exec_data,
            **resilience_data,
            **soc_data,
            **risk_quantification_data,
            "risk": {
                "risk_distribution": report.get("risk_distribution", {}),
                "top_risky_assets": report.get("top_risky_assets", []),
                "trends": trends,
            },
            "findings": report.get("critical_findings", []),
            "correlation": {
                "summary": report.get("summary", {}),
                "exposure_distribution": report.get("exposure_distribution", {}),
            },
            "priorities": {
                "top_assets": [ta.model_dump() for ta in top_assets],
                "top_findings": [tf.model_dump() for tf in top_findings],
                "top_technologies": [tt.model_dump() for tt in top_technologies],
                "top_products": [tp.model_dump() for tp in top_products],
            },
        }

    @classmethod
    async def _build_case_data(
        cls, db: AsyncSession, asset_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate case summaries, active lists, timelines, and linked evidence."""
        from src.services.case_service import CaseService
        from src.services.case_history_service import CaseHistoryService
        from src.services.case_evidence_correlation_service import CaseEvidenceCorrelationService
        from src.services.custody_service import CustodyService
        from src.services.case_snapshot_service import CaseSnapshotService

        cases = CaseService.get_all_cases()
        if asset_id:
            asset_cases = [c for c in cases if asset_id in c.asset_ids]
        else:
            asset_cases = cases

        active_cases_list = []
        for c in asset_cases:
            timeline = [
                {
                    "timestamp": h.timestamp.isoformat(),
                    "event_type": h.event_type,
                    "details": h.details,
                }
                for h in CaseHistoryService.get_history(c.case_id)
            ]

            correlated_evidence = CaseEvidenceCorrelationService.get_correlated_evidence(c.case_id, c.incident_ids)
            case_evidence_details = []
            for ev in correlated_evidence["case_evidence"]:
                custody_timeline = [
                    {
                        "entry_id": str(ch.entry_id),
                        "action": ch.action.value,
                        "actor": str(ch.actor),
                        "timestamp": ch.timestamp.isoformat(),
                        "notes": ch.notes,
                        "integrity_verified": ch.integrity_verified,
                    }
                    for ch in CustodyService.get_custody(ev.evidence_id)
                ]
                case_evidence_details.append({
                    "evidence_id": str(ev.evidence_id),
                    "source_entity": ev.source_entity,
                    "source_id": str(ev.source_id),
                    "integrity_hash": ev.integrity_hash,
                    "status": ev.status.value,
                    "collected_by": str(ev.collected_by),
                    "collected_at": ev.collected_at.isoformat(),
                    "chain_of_custody": custody_timeline,
                })

            active_cases_list.append(
                {
                    "case_id": str(c.case_id),
                    "case_fingerprint": c.case_fingerprint,
                    "title": c.title,
                    "description": c.description,
                    "severity": c.severity.value if hasattr(c.severity, "value") else str(c.severity),
                    "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                    "owner": str(c.owner) if c.owner else None,
                    "created_at": c.created_at.isoformat(),
                    "updated_at": c.updated_at.isoformat(),
                    "incident_ids": [str(iid) for iid in c.incident_ids],
                    "alert_ids": [str(aid) for aid in c.alert_ids],
                    "asset_ids": [str(asid) for asid in c.asset_ids],
                    "case_timeline": timeline,
                    "case_evidence": case_evidence_details,
                }
            )

        snapshot = CaseSnapshotService.get_snapshot(asset_id)

        return {
            "case_summary": snapshot,
            "active_cases": active_cases_list,
        }

    @classmethod
    async def _build_detection_data(cls) -> Dict[str, Any]:
        """Aggregate detection summary and coverage details."""
        from src.services.detection_service import DetectionService
        from src.services.detection_coverage_service import DetectionCoverageService
        from src.services.detection_snapshot_service import DetectionSnapshotService
        from src.domain.entities.detection import CoverageStatus, DetectionStatus

        detections = DetectionService.get_all_detections()
        coverage = DetectionCoverageService.calculate_coverage()
        overall_score = DetectionCoverageService.calculate_overall_score()
        snapshot = DetectionSnapshotService.get_snapshot()

        active_count = sum(1 for d in detections if d.status == DetectionStatus.ACTIVE)
        disabled_count = sum(1 for d in detections if d.status == DetectionStatus.DISABLED)
        deprecated_count = sum(1 for d in detections if d.status == DetectionStatus.DEPRECATED)

        covered_techniques = [
            c.technique_id for c in coverage if c.coverage_status == CoverageStatus.COVERED
        ]
        uncovered_techniques = [
            c.technique_id for c in coverage if c.coverage_status == CoverageStatus.NOT_COVERED
        ]
        coverage_gaps = uncovered_techniques

        detection_summary = {
            "total_detections": len(detections),
            "active_detections": active_count,
            "disabled_detections": disabled_count,
            "deprecated_detections": deprecated_count,
            "coverage_snapshot": snapshot,
        }

        return {
            "detection_summary": detection_summary,
            "coverage_score": overall_score,
            "covered_techniques": covered_techniques,
            "uncovered_techniques": uncovered_techniques,
            "coverage_gaps": coverage_gaps,
        }

    @classmethod
    async def build_case_context(
        cls, db: AsyncSession, case_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Aggregate context for a specific case."""
        from src.services.case_service import CaseService
        from src.services.case_history_service import CaseHistoryService
        from src.services.case_evidence_correlation_service import CaseEvidenceCorrelationService
        from src.services.custody_service import CustodyService

        case = CaseService.get_case(case_id)
        if not case:
            raise ValueError(f"Case {case_id} not found")

        timeline = [
            {
                "timestamp": h.timestamp.isoformat(),
                "event_type": h.event_type,
                "details": h.details,
            }
            for h in CaseHistoryService.get_history(case_id)
        ]

        correlated_evidence = CaseEvidenceCorrelationService.get_correlated_evidence(case_id, case.incident_ids)
        case_evidence_details = []
        for ev in correlated_evidence["case_evidence"]:
            custody_timeline = [
                {
                    "entry_id": str(ch.entry_id),
                    "action": ch.action.value,
                    "actor": str(ch.actor),
                    "timestamp": ch.timestamp.isoformat(),
                    "notes": ch.notes,
                    "integrity_verified": ch.integrity_verified,
                }
                for ch in CustodyService.get_custody(ev.evidence_id)
            ]
            case_evidence_details.append({
                "evidence_id": str(ev.evidence_id),
                "source_entity": ev.source_entity,
                "source_id": str(ev.source_id),
                "integrity_hash": ev.integrity_hash,
                "status": ev.status.value,
                "collected_by": str(ev.collected_by),
                "collected_at": ev.collected_at.isoformat(),
                "chain_of_custody": custody_timeline,
            })

        asset_context = {}
        scope_id = None
        if case.asset_ids:
            primary_asset_id = case.asset_ids[0]
            try:
                asset_context = await cls.build_asset_context(db, primary_asset_id)
                from src.infrastructure.database.models import Asset
                asset_obj = await db.get(Asset, primary_asset_id)
                scope_id = asset_obj.scope_id if asset_obj else None
            except Exception:
                pass

        th_data = await cls._build_threat_hunting_data(scope_id)
        pt_data = await cls._build_purple_team_data(scope_id)
        exposure_data = await cls._build_exposure_data(scope_id)
        posture_data = await cls._build_security_posture_context_block(scope_id)
        control_data = await cls._build_control_validation_context_block(scope_id)
        program_data = await cls._build_security_program_context_block(scope_id)
        exec_data = await cls._build_executive_reporting_context_block(scope_id)

        return {
            "context_version": CONTEXT_VERSION,
            "case_id": str(case.case_id),
            "case_fingerprint": case.case_fingerprint,
            "title": case.title,
            "description": case.description,
            "severity": case.severity.value if hasattr(case.severity, "value") else str(case.severity),
            "status": case.status.value if hasattr(case.status, "value") else str(case.status),
            "owner": str(case.owner) if case.owner else None,
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
            "incident_ids": [str(iid) for iid in case.incident_ids],
            "alert_ids": [str(aid) for aid in case.alert_ids],
            "asset_ids": [str(asid) for asid in case.asset_ids],
            "case_timeline": timeline,
            "case_evidence": case_evidence_details,
            "asset_context": asset_context,
            **th_data,
            **pt_data,
            **exposure_data,
            **posture_data,
            **control_data,
            **program_data,
            **exec_data,
        }

    @classmethod
    async def _build_exposure_data(
        cls, scope_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate Exposure Management summary, active exposures, attack surface categories, and drift statistics."""
        if scope_id and isinstance(scope_id, str):
            try:
                scope_id = uuid.UUID(scope_id)
            except ValueError:
                pass

        from src.services.exposure_snapshot_service import ExposureSnapshotService
        from src.services.exposure_service import ExposureService
        from src.services.exposure_history_service import ExposureHistoryService
        from src.services.exposure_correlation_service import ExposureCorrelationService

        snapshot = ExposureSnapshotService.get_snapshot(scope_id)
        exposures = ExposureService.get_all_exposures()

        active_exposures_list = []
        for e in exposures:
            if e.status.value in ["OPEN", "VALIDATED", "ACCEPTED", "MITIGATED"]:
                edata = ExposureService.to_response(e).model_dump()
                edata["exposure_id"] = str(e.exposure_id)
                edata["asset_id"] = str(e.asset_id)
                edata["history"] = [
                    {
                        "timestamp": h.timestamp.isoformat(),
                        "event_type": h.event_type,
                        "details": h.details,
                    }
                    for h in ExposureHistoryService.get_history(e.exposure_id)
                ]
                edata["correlations"] = ExposureCorrelationService.get_correlations(e.exposure_id)
                active_exposures_list.append(edata)

        return {
            "exposure_summary": snapshot["summary"],
            "active_exposures": active_exposures_list,
            "attack_surface_inventory": snapshot.get("attack_surface", {}),
        }

    @classmethod
    async def _build_security_posture_context_block(
        cls, scope_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate security posture summary, active postures, status counts, and trends."""
        if scope_id and isinstance(scope_id, str):
            try:
                scope_id = uuid.UUID(scope_id)
            except ValueError:
                pass

        from src.services.security_posture_snapshot_service import SecurityPostureSnapshotService
        from src.services.security_posture_service import SecurityPostureService
        from src.services.posture_history_service import PostureHistoryService
        from src.services.risk_correlation_service import RiskCorrelationService

        snapshot = SecurityPostureSnapshotService.get_snapshot(scope_id)
        postures = SecurityPostureService.get_all_postures()

        active_postures_list = []
        for p in postures:
            if p.status.value in ["OPEN", "ACCEPTED", "MITIGATED"]:
                pdata = SecurityPostureService.to_response(p).model_dump()
                pdata["posture_id"] = str(p.posture_id)
                pdata["asset_id"] = str(p.asset_id)
                pdata["history"] = [
                    {
                        "timestamp": h.timestamp.isoformat(),
                        "event_type": h.event_type,
                        "details": h.details,
                    }
                    for h in PostureHistoryService.get_history(p.posture_id)
                ]
                pdata["correlations"] = RiskCorrelationService.get_correlations(p.posture_id)
                active_postures_list.append(pdata)

        return {
            "security_posture_summary": snapshot["summary"],
            "active_postures": active_postures_list,
            "status_counts": snapshot.get("status_counts", {}),
        }

    @classmethod
    async def _build_global_security_posture_context_block(cls) -> Dict[str, Any]:
        """Aggregate global security posture summary across all scopes."""
        return await cls._build_security_posture_context_block(scope_id=None)

    @classmethod
    async def _build_control_validation_context_block(
        cls, scope_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate control validation summary, coverage, active controls, and status counts."""
        if scope_id and isinstance(scope_id, str):
            try:
                scope_id = uuid.UUID(scope_id)
            except ValueError:
                pass

        from src.services.control_validation_snapshot_service import ControlValidationSnapshotService
        from src.services.control_validation_service import ControlValidationService
        from src.services.control_history_service import ControlHistoryService
        from src.services.control_correlation_service import ControlCorrelationService

        snapshot = ControlValidationSnapshotService.get_snapshot(scope_id)
        controls = ControlValidationService.get_all_controls()

        active_controls_list = []
        for c in controls:
            if c.status.value in ["ACTIVE", "DEGRADED", "FAILED"]:
                cdata = ControlValidationService.to_response(c).model_dump()
                cdata["control_id"] = str(c.control_id)
                cdata["history"] = [
                    {
                        "timestamp": h.timestamp.isoformat(),
                        "event_type": h.event_type,
                        "details": h.details,
                    }
                    for h in ControlHistoryService.get_history(c.control_id)
                ]
                cdata["correlations"] = ControlCorrelationService.get_correlations(c.control_id)
                cdata["validations"] = [
                    {
                        "validation_id": str(v.validation_id),
                        "validation_status": v.validation_status.value,
                        "effectiveness_score": v.effectiveness_score,
                        "attack_technique": v.attack_technique,
                        "evidence": v.evidence,
                        "created_at": v.created_at.isoformat(),
                    }
                    for v in ControlValidationService.get_validations(c.control_id)
                ]
                active_controls_list.append(cdata)

        return {
            "control_validation_summary": snapshot["summary"],
            "control_coverage": snapshot.get("coverage", {}),
            "active_controls": active_controls_list,
        }

    @classmethod
    async def _build_global_control_validation_context_block(cls) -> Dict[str, Any]:
        """Aggregate global control validation summary across all scopes."""
        return await cls._build_control_validation_context_block(scope_id=None)

    @classmethod
    async def _build_security_program_context_block(
        cls, scope_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate security program summary and details for context."""
        if scope_id and isinstance(scope_id, str):
            try:
                scope_id = uuid.UUID(scope_id)
            except ValueError:
                pass

        from src.services.security_program_snapshot_service import SecurityProgramSnapshotService
        from src.services.security_program_service import SecurityProgramService
        from src.services.program_history_service import ProgramHistoryService
        from src.services.program_correlation_service import ProgramCorrelationService

        snapshot = SecurityProgramSnapshotService.get_snapshot(scope_id)
        programs = SecurityProgramService.get_all_programs()
        if scope_id:
            programs = [p for p in programs if p.scope_id == scope_id]

        programs_list = []
        for p in programs:
            pdata = SecurityProgramService.to_response(p).model_dump()
            pdata["program_id"] = str(p.program_id)
            pdata["history"] = [
                {
                    "timestamp": h.timestamp.isoformat(),
                    "event_type": h.event_type,
                    "details": h.details,
                }
                for h in ProgramHistoryService.get_history(p.program_id)
            ]
            pdata["correlations"] = ProgramCorrelationService.get_correlations(p.program_id)
            programs_list.append(pdata)

        return {
            "security_program_summary": snapshot["summary"],
            "security_programs": programs_list,
        }

    @classmethod
    async def _build_global_security_program_context_block(cls) -> Dict[str, Any]:
        """Aggregate global security program summary across all scopes."""
        return await cls._build_security_program_context_block(scope_id=None)

    @classmethod
    async def _build_executive_reporting_context_block(
        cls, scope_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate executive reporting summary and details for context."""
        if scope_id and isinstance(scope_id, str):
            try:
                scope_id = uuid.UUID(scope_id)
            except ValueError:
                pass

        from src.services.executive_snapshot_service import ExecutiveSnapshotService
        from src.services.executive_reporting_service import ExecutiveReportingService
        from src.services.executive_history_service import ExecutiveHistoryService

        snapshot = ExecutiveSnapshotService.get_snapshot(scope_id)
        reports = ExecutiveReportingService.get_all_reports()
        if scope_id:
            reports = [r for r in reports if r.scope_id == scope_id]

        reports_list = []
        for r in reports:
            rdata = ExecutiveReportingService.to_response(r).model_dump()
            rdata["report_id"] = str(r.report_id)
            rdata["history"] = [
                {
                    "timestamp": h.timestamp.isoformat(),
                    "event_type": h.event_type,
                    "details": h.details,
                }
                for h in ExecutiveHistoryService.get_history(r.report_id)
            ]
            reports_list.append(rdata)

        return {
            "executive_reporting_summary": snapshot["summary"],
            "executive_scorecard": snapshot["scorecard"],
            "executive_heatmap": snapshot["heatmap"],
            "executive_trends": snapshot["trends"],
            "executive_reports": reports_list,
        }

    @classmethod
    async def _build_global_executive_reporting_context_block(cls) -> Dict[str, Any]:
        """Aggregate global executive reporting summary across all scopes."""
        return await cls._build_executive_reporting_context_block(scope_id=None)

    @classmethod
    async def _build_cyber_resilience_context_block(
        cls, scope_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate cyber resilience summary and details for context."""
        if scope_id and isinstance(scope_id, str):
            try:
                scope_id = uuid.UUID(scope_id)
            except ValueError:
                pass

        from src.services.cyber_resilience_snapshot_service import CyberResilienceSnapshotService
        from src.services.cyber_resilience_service import CyberResilienceService
        from src.services.resilience_history_service import ResilienceHistoryService
        from src.services.recovery_objective_service import RecoveryObjectiveService

        snapshot = CyberResilienceSnapshotService.get_snapshot(scope_id)
        records = CyberResilienceService.get_all_resilience()
        if scope_id:
            records = [r for r in records if r.scope_id == scope_id]

        records_list = []
        for r in records:
            rdata = CyberResilienceService.to_response(r).model_dump()
            rdata["resilience_id"] = str(r.resilience_id)
            rdata["history"] = [
                {
                    "timestamp": h.timestamp.isoformat(),
                    "event_type": h.event_type,
                    "details": h.details,
                }
                for h in ResilienceHistoryService.get_history(r.resilience_id)
            ]
            rdata["objectives"] = [
                o.model_dump() for o in RecoveryObjectiveService.get_objectives(r.resilience_id)
            ]
            records_list.append(rdata)

        return {
            "resilience_summary": snapshot["summary"],
            "resilience_score": snapshot["summary"]["resilience_score"],
            "readiness_score": snapshot["summary"]["readiness_score"],
            "recovery_confidence_score": snapshot["summary"]["recovery_confidence_score"],
            "resilience_records": records_list,
        }

    @classmethod
    async def _build_global_cyber_resilience_context_block(cls) -> Dict[str, Any]:
        """Aggregate global cyber resilience summary across all scopes."""
        return await cls._build_cyber_resilience_context_block(scope_id=None)

    @classmethod
    async def _build_soc_context_block(
        cls, scope_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate SOC summary and details for context."""
        if scope_id and isinstance(scope_id, str):
            try:
                scope_id = uuid.UUID(scope_id)
            except ValueError:
                pass

        from src.services.soc_snapshot_service import SOCSnapshotService
        from src.services.security_operations_analytics_service import SecurityOperationsAnalyticsService
        from src.services.analytics_history_service import AnalyticsHistoryService

        snapshot = SOCSnapshotService.get_snapshot(scope_id)
        records = SecurityOperationsAnalyticsService.get_all_analytics()
        if scope_id:
            records = [r for r in records if r.scope_id == scope_id]

        records_list = []
        for r in records:
            rdata = SecurityOperationsAnalyticsService.to_response(r).model_dump()
            rdata["analytics_id"] = str(r.analytics_id)
            rdata["history"] = [
                {
                    "timestamp": h.timestamp.isoformat(),
                    "event_type": h.event_type,
                    "details": h.details,
                }
                for h in AnalyticsHistoryService.get_history(r.analytics_id)
            ]
            records_list.append(rdata)

        return {
            "analyst_performance_summary": snapshot["summary"],
            "queue_analytics_summary": {
                "queue_size": snapshot["summary"]["queue_size"],
                "processing_efficiency": snapshot["summary"]["queue_efficiency"],
            },
            "operational_kpis": snapshot["kpis"],
            "operational_kris": snapshot["kris"],
            "operational_health_score": snapshot["summary"]["operational_health_score"],
            "soc_drift_summary": {
                "total_records": snapshot["summary"]["total_analytics_records"],
                "active_records": snapshot["summary"]["active_analytics_records"],
            },
            "soc_analytics_records": records_list,
        }

    @classmethod
    async def _build_global_soc_context_block(cls) -> Dict[str, Any]:
        """Aggregate global SOC summary across all scopes."""
        return await cls._build_soc_context_block(scope_id=None)

    @classmethod
    async def _build_risk_quantification_context_block(
        cls, scope_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Aggregate Risk Quantification summary and details for context."""
        if scope_id and isinstance(scope_id, str):
            try:
                scope_id = uuid.UUID(scope_id)
            except ValueError:
                pass

        from src.services.risk_quantification_snapshot_service import RiskQuantificationSnapshotService
        from src.services.cyber_risk_quantification_service import CyberRiskQuantificationService
        from src.services.quantified_risk_history_service import QuantifiedRiskHistoryService
        from src.services.risk_forecast_service import RiskForecastService

        snapshot = RiskQuantificationSnapshotService.get_snapshot(scope_id)
        records = CyberRiskQuantificationService.get_all_risks()
        if scope_id:
            records = [r for r in records if r.scope_id == scope_id]

        records_list = []
        for r in records:
            rdata = CyberRiskQuantificationService.to_response(r).model_dump()
            rdata["risk_id"] = str(r.risk_id)
            rdata["history"] = [
                {
                    "timestamp": h.timestamp.isoformat(),
                    "event_type": h.event_type,
                    "details": h.details,
                }
                for h in QuantifiedRiskHistoryService.get_history(r.risk_id)
            ]
            rdata["forecasts"] = [
                f.model_dump()
                for f in RiskForecastService.get_forecasts(r.risk_id, r.annualized_loss_expectancy, r.exposure_value)
            ]
            records_list.append(rdata)

        return {
            "risk_quantification_summary": snapshot["summary"],
            "total_exposure_value": snapshot["summary"]["total_exposure_value"],
            "total_annualized_loss_expectancy": snapshot["summary"]["total_annualized_loss_expectancy"],
            "average_inherent_risk_score": snapshot["summary"]["average_inherent_risk_score"],
            "average_residual_risk_score": snapshot["summary"]["average_residual_risk_score"],
            "projected_loss_forecast": snapshot["summary"]["projected_loss_forecast"],
            "quantified_risks": records_list,
        }

    @classmethod
    async def _build_global_risk_quantification_context_block(cls) -> Dict[str, Any]:
        """Aggregate global Risk Quantification summary across all scopes."""
        return await cls._build_risk_quantification_context_block(scope_id=None)
