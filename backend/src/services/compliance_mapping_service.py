import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.governance import ComplianceControlResponse
from src.infrastructure.database.models import Asset, Finding, AssetPort
from src.services.compliance_control_registry import CONTROL_MAPPINGS, CONTROL_DETAILS
from src.services.remediation_service import RemediationService
from src.services.risk_acceptance_service import RiskAcceptanceService, RiskAcceptanceStatus
from src.services.sla_monitoring_service import SLAMonitoringService


class ComplianceMappingService:
    @classmethod
    async def get_compliance_controls(cls, db: AsyncSession) -> List[ComplianceControlResponse]:
        """Evaluate all compliance controls and map assets and findings to them."""
        # 1. Fetch all active assets and findings
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        res_assets = await db.execute(q_assets)
        assets = res_assets.scalars().all()

        q_findings = select(Finding).where(Finding.status == "open")
        res_findings = await db.execute(q_findings)
        findings = res_findings.scalars().all()

        now = datetime.now(timezone.utc)

        # Build maps of active exemptions/acceptances by recommendation fingerprint
        active_acceptances = RiskAcceptanceService.get_active_acceptances()
        active_fingerprints = {a.recommendation_fingerprint for a in active_acceptances}

        # Also get exceptions from RemediationService
        remediations = RemediationService.get_all_remediations()
        exempted_fingerprints = {
            r.recommendation_fingerprint
            for r in remediations
            if r.status.value in ["ACCEPTED_RISK", "FALSE_POSITIVE", "DEFERRED"]
        }

        # All covered fingerprints
        covered_fingerprints = active_fingerprints.union(exempted_fingerprints)

        # Maps for each control ID: list of affected assets, list of affected findings
        failures: Dict[str, Dict[str, List[uuid.UUID]]] = {
            "VULN-001": {"assets": [], "findings": []},
            "EXP-001": {"assets": [], "findings": []},
            "OPS-001": {"assets": [], "findings": []},
            "GOV-001": {"assets": [], "findings": []},
        }

        # Check VULN-001: Critical findings
        for f in findings:
            if f.severity.lower() == "critical" and f.fingerprint not in covered_fingerprints:
                failures["VULN-001"]["findings"].append(f.id)
                if f.asset_id not in failures["VULN-001"]["assets"]:
                    failures["VULN-001"]["assets"].append(f.asset_id)

        # Check EXP-001: Internet-exposed admin services
        # We check open ports (22, 23, 21, 3389, 445) on internet exposed assets
        from src.services.correlation_service import CorrelationService

        for asset in assets:
            # Check exposure
            asset_info = await CorrelationService.correlate_asset(db, asset.id)
            is_exposed = asset_info.get("exposure") == "external"

            if is_exposed:
                # Fetch open ports
                q_ports = select(AssetPort).where(
                    AssetPort.asset_id == asset.id,
                    AssetPort.state == "open"
                )
                res_ports = await db.execute(q_ports)
                ports = res_ports.scalars().all()

                admin_ports = [p.port for p in ports if p.port in [21, 22, 23, 445, 3389]]
                if admin_ports:
                    # Check if there is any finding/remediation covered
                    # If any open finding exists for this asset and is not covered, it's non-compliant
                    asset_findings = [f for f in findings if f.asset_id == asset.id]
                    uncovered = [f for f in asset_findings if f.fingerprint not in covered_fingerprints]
                    
                    # If any admin port is exposed, mark the asset non-compliant
                    failures["EXP-001"]["assets"].append(asset.id)
                    for f in uncovered:
                        if any(term in f.title.lower() for term in ["port", "ssh", "ftp", "telnet", "rdp", "smb"]):
                            failures["EXP-001"]["findings"].append(f.id)

        # Check OPS-001: SLA breaches
        for r in remediations:
            if r.status.value in ["OPEN", "IN_PROGRESS", "DEFERRED"]:
                is_breached = r.due_date < now
                if is_breached and r.recommendation_fingerprint not in active_fingerprints:
                    failures["OPS-001"]["assets"].append(r.asset_id)
                    if r.finding_id:
                        failures["OPS-001"]["findings"].append(r.finding_id)

        # Check GOV-001: Expired/Revoked Risk Acceptances
        all_acceptances = RiskAcceptanceService.get_all_acceptances()
        for a in all_acceptances:
            if a.status in [RiskAcceptanceStatus.EXPIRED, RiskAcceptanceStatus.REVOKED]:
                # If there's no active replacement for this fingerprint, it's non-compliant
                has_active = any(
                    other.recommendation_fingerprint == a.recommendation_fingerprint
                    and other.status in [RiskAcceptanceStatus.ACTIVE, RiskAcceptanceStatus.EXPIRING]
                    for other in all_acceptances
                )
                if not has_active:
                    failures["GOV-001"]["assets"].append(a.asset_id)
                    if a.finding_id:
                        failures["GOV-001"]["findings"].append(a.finding_id)

        # Format responses
        responses = []
        for cid, details in CONTROL_DETAILS.items():
            c_fails = failures.get(cid, {"assets": [], "findings": []})
            has_fails = len(c_fails["assets"]) > 0 or len(c_fails["findings"]) > 0
            responses.append(
                ComplianceControlResponse(
                    control_id=cid,
                    control_name=details["name"],
                    status="NON_COMPLIANT" if has_fails else "COMPLIANT",
                    severity=details["severity"],
                    affected_assets=c_fails["assets"],
                    affected_findings=c_fails["findings"],
                )
            )

        return responses
