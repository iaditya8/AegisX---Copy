import uuid
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.governance import GovernanceStatus
from src.infrastructure.database.models import Asset, Finding
from src.services.compliance_mapping_service import ComplianceMappingService
from src.services.remediation_service import RemediationService
from src.services.risk_acceptance_service import (
    RiskAcceptanceService,
    RiskAcceptanceStatus,
)


class GovernanceService:
    @classmethod
    async def evaluate_finding_governance(
        cls, db: AsyncSession, finding_id: uuid.UUID
    ) -> GovernanceStatus:
        """Evaluate governance status of an individual finding."""
        finding = await db.get(Finding, finding_id)
        if not finding:
            raise ValueError(f"Finding {finding_id} not found")

        if finding.status != "open":
            return GovernanceStatus.COMPLIANT

        # Check in-memory risk acceptances for finding.fingerprint
        acceptances = RiskAcceptanceService.get_all_acceptances()
        active_acc = [
            a
            for a in acceptances
            if a.recommendation_fingerprint == finding.fingerprint
            and a.status in [RiskAcceptanceStatus.ACTIVE, RiskAcceptanceStatus.EXPIRING]
        ]
        if active_acc:
            return GovernanceStatus.ACCEPTED_RISK

        # Check exception status in RemediationService
        remediations = RemediationService.get_all_remediations()
        rem = next(
            (
                r
                for r in remediations
                if r.recommendation_fingerprint == finding.fingerprint
            ),
            None,
        )
        if rem:
            if rem.status.value in ["ACCEPTED_RISK"]:
                return GovernanceStatus.ACCEPTED_RISK
            elif rem.status.value in ["FALSE_POSITIVE", "DEFERRED"]:
                return GovernanceStatus.EXCEPTION_ACTIVE
            elif rem.status.value == "IN_PROGRESS":
                return GovernanceStatus.UNDER_REVIEW

        return GovernanceStatus.NON_COMPLIANT

    @classmethod
    async def evaluate_asset_governance(
        cls, db: AsyncSession, asset_id: uuid.UUID
    ) -> GovernanceStatus:
        """Evaluate overall governance status of a given asset."""
        # 1. Fetch asset findings
        q_findings = select(Finding).where(
            Finding.asset_id == asset_id, Finding.status == "open"
        )
        res_findings = await db.execute(q_findings)
        findings = res_findings.scalars().all()

        if not findings:
            # Check if there are SLA breaches on resolved findings' remediations (if any)
            remediations = RemediationService.get_remediations_by_asset(asset_id)
            active_rems = [
                r
                for r in remediations
                if r.status.value in ["OPEN", "IN_PROGRESS", "DEFERRED"]
            ]
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
            has_breach = any(r.due_date < now for r in active_rems)
            if has_breach:
                return GovernanceStatus.NON_COMPLIANT
            return GovernanceStatus.COMPLIANT

        # Check compliance mapping controls
        controls = await ComplianceMappingService.get_compliance_controls(db)
        is_non_compliant = False
        for c in controls:
            if asset_id in c.affected_assets:
                is_non_compliant = True
                break

        if is_non_compliant:
            return GovernanceStatus.NON_COMPLIANT

        # If not non-compliant, check if they are all accepted/exempted
        finding_statuses = []
        for f in findings:
            status = await cls.evaluate_finding_governance(db, f.id)
            finding_statuses.append(status)

        if all(s == GovernanceStatus.COMPLIANT for s in finding_statuses):
            return GovernanceStatus.COMPLIANT

        if any(s == GovernanceStatus.ACCEPTED_RISK for s in finding_statuses):
            return GovernanceStatus.ACCEPTED_RISK

        if any(s == GovernanceStatus.EXCEPTION_ACTIVE for s in finding_statuses):
            return GovernanceStatus.EXCEPTION_ACTIVE

        if any(s == GovernanceStatus.UNDER_REVIEW for s in finding_statuses):
            return GovernanceStatus.UNDER_REVIEW

        return GovernanceStatus.NON_COMPLIANT

    @classmethod
    async def get_non_compliant_assets(cls, db: AsyncSession) -> List[Asset]:
        """Retrieve all assets that are currently evaluated as NON_COMPLIANT."""
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        res_assets = await db.execute(q_assets)
        assets = res_assets.scalars().all()

        non_compliant = []
        for asset in assets:
            status = await cls.evaluate_asset_governance(db, asset.id)
            if status == GovernanceStatus.NON_COMPLIANT:
                non_compliant.append(asset)
        return non_compliant

    @classmethod
    async def get_non_compliant_findings(cls, db: AsyncSession) -> List[Finding]:
        """Retrieve all findings that are currently evaluated as NON_COMPLIANT."""
        q_findings = select(Finding).where(Finding.status == "open")
        res_findings = await db.execute(q_findings)
        findings = res_findings.scalars().all()

        non_compliant = []
        for f in findings:
            status = await cls.evaluate_finding_governance(db, f.id)
            if status == GovernanceStatus.NON_COMPLIANT:
                non_compliant.append(f)
        return non_compliant

    @classmethod
    async def evaluate_platform_governance(cls, db: AsyncSession) -> Dict[str, Any]:
        """Evaluate organization-wide compliance and return aggregated summary."""
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        res_assets = await db.execute(q_assets)
        assets = res_assets.scalars().all()

        compliant_count = 0
        non_compliant_count = 0
        accepted_count = 0

        for asset in assets:
            status = await cls.evaluate_asset_governance(db, asset.id)
            if status == GovernanceStatus.COMPLIANT:
                compliant_count += 1
            elif status == GovernanceStatus.NON_COMPLIANT:
                non_compliant_count += 1
            elif status in [
                GovernanceStatus.ACCEPTED_RISK,
                GovernanceStatus.EXCEPTION_ACTIVE,
            ]:
                accepted_count += 1

        active_acceptances = RiskAcceptanceService.get_active_acceptances()
        expired_count = len(
            [
                a
                for a in RiskAcceptanceService.get_all_acceptances()
                if a.status == RiskAcceptanceStatus.EXPIRED
            ]
        )

        remediations = RemediationService.get_all_remediations()
        exceptions_count = len(
            [
                r
                for r in remediations
                if r.status.value in ["ACCEPTED_RISK", "FALSE_POSITIVE", "DEFERRED"]
            ]
        )

        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        sla_breach_count = len(
            [
                r
                for r in remediations
                if r.status.value in ["OPEN", "IN_PROGRESS", "DEFERRED"]
                and r.due_date < now
            ]
        )

        return {
            "compliant_assets": compliant_count,
            "non_compliant_assets": non_compliant_count,
            "accepted_risks": len(active_acceptances),
            "expired_acceptances": expired_count,
            "exception_count": exceptions_count,
            "sla_breaches": sla_breach_count,
        }
