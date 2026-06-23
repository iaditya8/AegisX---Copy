import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.recommendation import InvestigationGuidanceResponse
from src.infrastructure.database.models import Asset, Finding
from src.services.asset_risk_snapshot_service import AssetRiskSnapshotService
from src.services.correlation_snapshot_service import CorrelationSnapshotService


class InvestigationAssistanceService:
    @classmethod
    async def generate_asset_guidance(
        cls, db: AsyncSession, asset_id: uuid.UUID
    ) -> InvestigationGuidanceResponse:
        """Generate investigation steps for an asset based on risk context."""
        asset = await db.get(Asset, asset_id)
        if not asset or asset.deleted_at is not None:
            raise ValueError("Asset not found")

        risk_snapshot = AssetRiskSnapshotService.get_snapshot(asset_id)
        corr_snapshot = CorrelationSnapshotService.get_snapshot(asset_id)

        steps = []

        # 1. Fetch active findings
        q = select(Finding).where(
            Finding.asset_id == asset_id,
            Finding.status.in_(["open", "acknowledged"]),
        )
        res = await db.execute(q)
        findings = res.scalars().all()

        has_critical = any(f.severity.lower() == "critical" for f in findings)
        has_high = any(f.severity.lower() == "high" for f in findings)

        if has_critical:
            steps.extend(
                [
                    "Verify if the critical vulnerability is exposed to the internet.",
                    "Investigate logs for active exploitation attempts.",
                    "Identify active processes associated with the vulnerable service.",
                ]
            )

        if has_high:
            steps.extend(
                [
                    "Verify patch levels for the affected software.",
                    "Restrict network access to the port hosting the service.",
                ]
            )

        # 2. Rediscovered findings
        has_rediscovered = False
        for f in findings:
            if f.first_seen is not None and f.last_seen is not None:
                fs = (
                    f.first_seen.replace(tzinfo=None)
                    if hasattr(f.first_seen, "replace")
                    else f.first_seen
                )
                ls = (
                    f.last_seen.replace(tzinfo=None)
                    if hasattr(f.last_seen, "replace")
                    else f.last_seen
                )
                if ls > fs:
                    has_rediscovered = True
                    break

        if has_rediscovered:
            steps.extend(
                [
                    "Review past resolution records for recurrent patterns.",
                    "Investigate if recent configuration updates rolled back patches.",
                ]
            )

        # 3. External asset exposure
        exposure = corr_snapshot.get("exposure", "UNKNOWN")
        if exposure.upper() == "EXTERNAL":
            steps.extend(
                [
                    "Audit ingress firewall rules to minimize public exposure.",
                    "Ensure robust service banners are configured.",
                ]
            )

        # 4. High risk asset
        risk_score = risk_snapshot.get("risk_score", 0)
        if risk_score >= 80:
            steps.extend(
                [
                    "Schedule immediate vulnerability remediation scan.",
                    "Perform full system memory and disk threat hunt.",
                    "Review active user accounts and permission sets on the host.",
                ]
            )

        # Default fallback steps if no conditions match
        if not steps:
            steps.extend(
                [
                    "Perform baseline configuration review.",
                    "Ensure standard scanning credentials are valid.",
                ]
            )

        # De-duplicate maintaining order
        unique_steps = []
        for s in steps:
            if s not in unique_steps:
                unique_steps.append(s)

        return InvestigationGuidanceResponse(
            finding_id=None, asset_id=str(asset_id), steps=unique_steps
        )

    @classmethod
    async def generate_finding_guidance(
        cls, db: AsyncSession, finding_id: uuid.UUID
    ) -> InvestigationGuidanceResponse:
        """Generate investigation steps for a finding based on severity and status."""
        finding = await db.get(Finding, finding_id)
        if not finding:
            raise ValueError("Finding not found")

        steps = []

        if finding.severity.lower() == "critical":
            steps.extend(
                [
                    "Verify exploitability using non-intrusive security tools.",
                    "Inspect traffic logs matching the target port for anomalies.",
                    "Identify the process owner running the vulnerable service.",
                ]
            )
        elif finding.severity.lower() == "high":
            steps.extend(
                [
                    "Verify finding details against vendor vulnerability bulletins.",
                    "Audit network paths leading to the exposed vulnerable port.",
                ]
            )
        else:
            steps.extend(
                [
                    "Monitor finding status and verify during the next scheduled scan.",
                    "Validate standard software patch cycles for resolution.",
                ]
            )

        # Rediscovered check
        if finding.first_seen is not None and finding.last_seen is not None:
            fs = (
                finding.first_seen.replace(tzinfo=None)
                if hasattr(finding.first_seen, "replace")
                else finding.first_seen
            )
            ls = (
                finding.last_seen.replace(tzinfo=None)
                if hasattr(finding.last_seen, "replace")
                else finding.last_seen
            )
            if ls > fs:
                steps.extend(
                    [
                        "Verify why previous resolution status did not persist.",
                        "Inspect system state updates to locate rolled-back configs.",
                    ]
                )

        # De-duplicate maintaining order
        unique_steps = []
        for s in steps:
            if s not in unique_steps:
                unique_steps.append(s)

        return InvestigationGuidanceResponse(
            finding_id=str(finding_id),
            asset_id=str(finding.asset_id),
            steps=unique_steps,
        )
