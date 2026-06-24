import uuid
from typing import Any, Dict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Finding, FindingEvidence
from src.services.asset_report_service import AssetReportService
from src.services.dashboard_trend_service import DashboardTrendService
from src.services.executive_report_service import ExecutiveReportService

CONTEXT_VERSION = "1.0"


class AIContextBuilder:
    @classmethod
    async def _build_governance_data(cls, db: AsyncSession, asset_id: uuid.UUID) -> Dict[str, Any]:
        """Aggregate governance statistics and status for an asset."""
        from src.services.governance_service import GovernanceService
        from src.services.risk_acceptance_service import RiskAcceptanceService, RiskAcceptanceStatus
        from src.services.compliance_mapping_service import ComplianceMappingService
        from src.services.remediation_service import RemediationService

        gov_status = await GovernanceService.evaluate_asset_governance(db, asset_id)
        asset_acceptances = RiskAcceptanceService.get_acceptances_by_asset(asset_id)
        
        active_acc = [a.recommendation_fingerprint for a in asset_acceptances if a.status in [RiskAcceptanceStatus.ACTIVE, RiskAcceptanceStatus.EXPIRING]]
        expired_acc = [a.recommendation_fingerprint for a in asset_acceptances if a.status == RiskAcceptanceStatus.EXPIRED]

        controls = await ComplianceMappingService.get_compliance_controls(db)
        failed_controls = [c.control_id for c in controls if asset_id in c.affected_assets]

        remediations = RemediationService.get_remediations_by_asset(asset_id)
        now = datetime.now(timezone.utc)
        sla_breaches = [
            str(r.remediation_id) for r in remediations 
            if r.status.value in ["OPEN", "IN_PROGRESS", "DEFERRED"] and r.due_date < now
        ]

        return {
            "governance_status": gov_status.value,
            "accepted_risks": active_acc,
            "expired_acceptances": expired_acc,
            "compliance_controls": failed_controls,
            "sla_breaches": sla_breaches,
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
            },
            "governance": gov_data,
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
            },
            "governance": gov_data,
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

        from src.services.prioritization_service import PrioritizationService
        from src.services.governance_snapshot_service import GovernanceSnapshotService

        top_assets = await PrioritizationService.get_top_assets(db, limit=10)
        top_findings = await PrioritizationService.get_top_findings(db, limit=20)
        top_technologies = await PrioritizationService.get_top_technologies(
            db, limit=20
        )
        top_products = await PrioritizationService.get_top_products(db, limit=20)
        gov_snapshot = await GovernanceSnapshotService.get_snapshot(db)

        return {
            "context_version": CONTEXT_VERSION,
            "asset": {},
            "governance": gov_snapshot,
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
