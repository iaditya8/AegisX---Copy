import uuid
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Asset, AssetPort, AssetService, Finding
from src.services.asset_exposure_service import (
    AssetExposureService,
    ExposureClassification,
)


class CorrelationService:
    """Service to generate a unified correlation snapshot for an asset."""

    @classmethod
    async def correlate_asset(
        cls, db: AsyncSession, asset_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Correlate asset records, ports, services, findings, and calculate risk factors."""
        # 1. Fetch asset
        asset = await db.get(Asset, asset_id)
        if not asset:
            # Handle empty/missing asset gracefully
            return {
                "asset_id": str(asset_id),
                "ports": [],
                "services": [],
                "technologies": [],
                "products": [],
                "finding_counts": {
                    "info": 0,
                    "low": 0,
                    "medium": 0,
                    "high": 0,
                    "critical": 0,
                },
                "exposure": "UNKNOWN",
                "risk_factors": [],
            }

        # 2. Exposure Classification
        exposure = AssetExposureService.classify(asset)

        # 3. Retrieve Ports & Services
        q_ports = select(AssetPort).where(
            AssetPort.asset_id == asset_id, AssetPort.state == "open"
        )
        res_ports = await db.execute(q_ports)
        open_ports = res_ports.scalars().all()
        port_ids = [p.id for p in open_ports]

        ports_list = [f"{p.port}/{p.protocol}" for p in open_ports]

        services_list = []
        technologies = set()
        products = set()

        if port_ids:
            q_services = select(AssetService).where(
                AssetService.asset_port_id.in_(port_ids)
            )
            res_services = await db.execute(q_services)
            services = res_services.scalars().all()
            for s in services:
                if s.service_name:
                    services_list.append(s.service_name)
                if s.product:
                    technologies.add(s.product)
                    products.add(s.product)

        # 4. Fetch Active Findings (open or acknowledged, not closed_by_scan)
        q_findings = select(Finding).where(
            Finding.asset_id == asset_id, Finding.status.in_(["open", "acknowledged"])
        )
        res_findings = await db.execute(q_findings)
        findings = res_findings.scalars().all()

        finding_counts = {"info": 0, "low": 0, "medium": 0, "high": 0, "critical": 0}
        for f in findings:
            meta = f.metadata_json or {}
            if not meta.get("closed_by_scan", False):
                sev = f.severity.lower()
                if sev in finding_counts:
                    finding_counts[sev] += 1

        # 5. Evaluate Risk Factors
        risk_factors = []

        # internet_exposed
        if exposure == ExposureClassification.EXTERNAL:
            risk_factors.append("internet_exposed")

        # critical_finding_present
        if finding_counts.get("critical", 0) > 0:
            risk_factors.append("critical_finding_present")

        # high_finding_count (total active findings >= 5)
        total_findings = sum(finding_counts.values())
        if total_findings >= 5:
            risk_factors.append("high_finding_count")

        # multiple_open_ports (>= 3 open ports)
        if len(ports_list) >= 3:
            risk_factors.append("multiple_open_ports")

        # multiple_services (>= 3 services)
        if len(services_list) >= 3:
            risk_factors.append("multiple_services")

        # high_attack_surface (external and either multiple ports/services, or >=5 ports)
        if exposure == ExposureClassification.EXTERNAL and (
            len(ports_list) >= 3 or len(services_list) >= 3
        ):
            risk_factors.append("high_attack_surface")
        elif len(ports_list) >= 5:
            risk_factors.append("high_attack_surface")

        return {
            "asset_id": str(asset_id),
            "ports": sorted(ports_list),
            "services": sorted(services_list),
            "technologies": sorted(list(technologies)),
            "products": sorted(list(products)),
            "finding_counts": finding_counts,
            "exposure": exposure.value,
            "risk_factors": risk_factors,
        }
