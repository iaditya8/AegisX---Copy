import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.recommendation import RecommendationResponse, SupportingFactor
from src.infrastructure.database.models import Asset, Finding
from src.services.asset_risk_snapshot_service import AssetRiskSnapshotService
from src.services.correlation_snapshot_service import CorrelationSnapshotService
from src.services.prioritization_service import PrioritizationService
from src.services.recommendation_fingerprint_service import (
    RecommendationFingerprintService,
)
from src.services.recommendation_history_service import RecommendationHistoryService
from src.services.recommendation_rules_registry import RecommendationRulesRegistry


class RecommendationService:
    @classmethod
    async def generate_asset_recommendations(
        cls, db: AsyncSession, asset_id: uuid.UUID
    ) -> List[RecommendationResponse]:
        """Generate remediation recommendations for a given asset and
        its active findings.
        """
        asset = await db.get(Asset, asset_id)
        if not asset or asset.deleted_at is not None:
            return []

        risk_snapshot = AssetRiskSnapshotService.get_snapshot(asset_id)
        if (
            risk_snapshot.get("exposure") == "UNKNOWN"
            and risk_snapshot.get("risk_score") == 0
        ):
            risk_snapshot = await AssetRiskSnapshotService.generate_snapshot(
                db, asset_id
            )

        corr_snapshot = CorrelationSnapshotService.get_snapshot(asset_id)
        if corr_snapshot.get("exposure") == "UNKNOWN" and not corr_snapshot.get(
            "ports"
        ):
            corr_snapshot = await CorrelationSnapshotService.generate_snapshot(
                db, asset_id
            )

        recommendations = []

        # 1. High risk asset rule (risk_score >= 80)
        score, factors = await PrioritizationService.calculate_asset_priority(db, asset)
        if risk_snapshot.get("risk_score", 0) >= 80:
            rule = RecommendationRulesRegistry.get_rule("high_risk_asset")
            if rule:
                title = rule["title"]
                r_type = rule["type"]
                priority = rule["priority"]
                fp = RecommendationFingerprintService.generate_fingerprint(
                    str(asset_id), None, r_type, title
                )

                await RecommendationHistoryService.record_recommendation(
                    db=db,
                    fingerprint=fp,
                    asset_id=str(asset_id),
                    finding_id=None,
                    priority=priority,
                    title=title,
                )

                supporting_factors = [
                    SupportingFactor(factor=f["factor"], impact=f["impact"])
                    for f in factors
                ]

                recommendations.append(
                    RecommendationResponse(
                        recommendation_id=fp,
                        priority=priority,
                        type=r_type,
                        asset_id=str(asset_id),
                        finding_id=None,
                        title=title,
                        reason=rule["reason"],
                        risk_score=score,
                        supporting_factors=supporting_factors,
                    )
                )

        # 2. Findings level rules
        q = select(Finding).where(
            Finding.asset_id == asset_id,
            Finding.status.in_(["open", "acknowledged"]),
        )
        res = await db.execute(q)
        findings = res.scalars().all()

        for f in findings:
            f_score, f_factors = await PrioritizationService.calculate_finding_priority(
                db, f, parent_asset=asset
            )

            # Evaluate state rules
            exposure = corr_snapshot.get("exposure", "UNKNOWN")
            is_external = exposure.upper() == "EXTERNAL"
            is_critical = f.severity.lower() == "critical"

            rule_key = None
            if is_external and is_critical:
                rule_key = "external_critical_finding"
            elif (
                f.first_seen is not None
                and f.last_seen is not None
                and (
                    (
                        f.last_seen.replace(tzinfo=None)
                        if hasattr(f.last_seen, "replace")
                        else f.last_seen
                    )
                    > (
                        f.first_seen.replace(tzinfo=None)
                        if hasattr(f.first_seen, "replace")
                        else f.first_seen
                    )
                )
            ):
                rule_key = "rediscovered_finding"
            else:
                sev_key = f"{f.severity.lower()}_finding"
                if RecommendationRulesRegistry.get_rule(sev_key):
                    rule_key = sev_key

            if rule_key:
                rule = RecommendationRulesRegistry.get_rule(rule_key)
                if rule:
                    title = rule["title"]
                    r_type = rule["type"]
                    priority = rule["priority"]
                    fp = RecommendationFingerprintService.generate_fingerprint(
                        str(asset_id), str(f.id), r_type, title
                    )

                    await RecommendationHistoryService.record_recommendation(
                        db=db,
                        fingerprint=fp,
                        asset_id=str(asset_id),
                        finding_id=str(f.id),
                        priority=priority,
                        title=title,
                    )

                    supporting_factors = [
                        SupportingFactor(factor=f_fac["factor"], impact=f_fac["impact"])
                        for f_fac in f_factors
                    ]

                    recommendations.append(
                        RecommendationResponse(
                            recommendation_id=fp,
                            priority=priority,
                            type=r_type,
                            asset_id=str(asset_id),
                            finding_id=str(f.id),
                            title=title,
                            reason=rule["reason"],
                            risk_score=f_score,
                            supporting_factors=supporting_factors,
                        )
                    )

        return recommendations

    @classmethod
    async def generate_finding_recommendations(
        cls, db: AsyncSession, finding_id: uuid.UUID
    ) -> List[RecommendationResponse]:
        """Generate remediation recommendations for a specific finding."""
        finding = await db.get(Finding, finding_id)
        if not finding or finding.status not in ["open", "acknowledged"]:
            return []

        asset = await db.get(Asset, finding.asset_id)
        if not asset or asset.deleted_at is not None:
            return []

        corr_snapshot = CorrelationSnapshotService.get_snapshot(asset.id)
        f_score, f_factors = await PrioritizationService.calculate_finding_priority(
            db, finding, parent_asset=asset
        )

        exposure = corr_snapshot.get("exposure", "UNKNOWN")
        is_external = exposure.upper() == "EXTERNAL"
        is_critical = finding.severity.lower() == "critical"

        rule_key = None
        if is_external and is_critical:
            rule_key = "external_critical_finding"
        elif (
            finding.first_seen is not None
            and finding.last_seen is not None
            and (
                (
                    finding.last_seen.replace(tzinfo=None)
                    if hasattr(finding.last_seen, "replace")
                    else finding.last_seen
                )
                > (
                    finding.first_seen.replace(tzinfo=None)
                    if hasattr(finding.first_seen, "replace")
                    else finding.first_seen
                )
            )
        ):
            rule_key = "rediscovered_finding"
        else:
            sev_key = f"{finding.severity.lower()}_finding"
            if RecommendationRulesRegistry.get_rule(sev_key):
                rule_key = sev_key

        if not rule_key:
            return []

        rule = RecommendationRulesRegistry.get_rule(rule_key)
        if not rule:
            return []

        title = rule["title"]
        r_type = rule["type"]
        priority = rule["priority"]
        fp = RecommendationFingerprintService.generate_fingerprint(
            str(asset.id), str(finding_id), r_type, title
        )

        await RecommendationHistoryService.record_recommendation(
            db=db,
            fingerprint=fp,
            asset_id=str(asset.id),
            finding_id=str(finding_id),
            priority=priority,
            title=title,
        )

        supporting_factors = [
            SupportingFactor(factor=f_fac["factor"], impact=f_fac["impact"])
            for f_fac in f_factors
        ]

        return [
            RecommendationResponse(
                recommendation_id=fp,
                priority=priority,
                type=r_type,
                asset_id=str(asset.id),
                finding_id=str(finding_id),
                title=title,
                reason=rule["reason"],
                risk_score=f_score,
                supporting_factors=supporting_factors,
            )
        ]
