import uuid
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Finding, FindingEvidence
from src.services.asset_report_service import AssetReportService
from src.services.dashboard_trend_service import DashboardTrendService
from src.services.executive_report_service import ExecutiveReportService

CONTEXT_VERSION = "1.0"


class AIContextBuilder:
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

        recs = await RecommendationService.generate_asset_recommendations(db, asset_id)
        rec_snapshot = RecommendationSnapshotService.get_snapshot(asset_id)

        return {
            "context_version": CONTEXT_VERSION,
            "asset": {
                **report["asset"],
                "ports": report.get("ports", []),
                "services": report.get("services", []),
                "technologies": report.get("technologies", []),
                "recommendation_snapshot": rec_snapshot,
            },
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
        }

        # Fetch asset report for contextual asset details
        report = await AssetReportService.generate_asset_report(db, finding.asset_id)
        if not report:
            raise ValueError(
                f"Asset {finding.asset_id} associated with finding "
                f"{finding_id} not found"
            )

        from src.services.recommendation_service import RecommendationService
        from src.services.recommendation_snapshot_service import (
            RecommendationSnapshotService,
        )

        recs = await RecommendationService.generate_finding_recommendations(
            db, finding_id
        )
        rec_snapshot = RecommendationSnapshotService.get_snapshot(finding.asset_id)

        return {
            "context_version": CONTEXT_VERSION,
            "asset": {
                **report["asset"],
                "ports": report.get("ports", []),
                "services": report.get("services", []),
                "technologies": report.get("technologies", []),
                "recommendation_snapshot": rec_snapshot,
            },
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

        top_assets = await PrioritizationService.get_top_assets(db, limit=10)
        top_findings = await PrioritizationService.get_top_findings(db, limit=20)
        top_technologies = await PrioritizationService.get_top_technologies(
            db, limit=20
        )
        top_products = await PrioritizationService.get_top_products(db, limit=20)

        return {
            "context_version": CONTEXT_VERSION,
            "asset": {},
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
