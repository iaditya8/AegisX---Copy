import uuid
from enum import Enum
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Asset, AssetPort, AssetService, Finding
from src.services.asset_exposure_service import (
    AssetExposureService,
    ExposureClassification,
)
from src.services.criticality_factor_registry import CRITICALITY_FACTORS


class AssetCriticality(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AssetCriticalityService:
    """Service to calculate asset criticality score and level."""

    @classmethod
    async def calculate_asset_criticality(
        cls, db: AsyncSession, asset_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Determine criticality based on exposure, services, technologies,
        and findings.
        """
        asset = await db.get(Asset, asset_id)
        if not asset:
            return {
                "criticality": AssetCriticality.LOW,
                "score": 0,
                "reasons": ["Asset not found"],
            }

        # 1. Classify exposure
        exposure = AssetExposureService.classify(asset)

        # 2. Get service and technology counts
        q_ports = select(AssetPort).where(
            AssetPort.asset_id == asset_id, AssetPort.state == "open"
        )
        res_ports = await db.execute(q_ports)
        open_ports = res_ports.scalars().all()
        port_ids = [p.id for p in open_ports]

        service_count = 0
        tech_count = 0
        if port_ids:
            q_services = select(AssetService).where(
                AssetService.asset_port_id.in_(port_ids)
            )
            res_services = await db.execute(q_services)
            services = res_services.scalars().all()
            service_count = len(services)

            technologies = set()
            for svc in services:
                if svc.product:
                    technologies.add(svc.product)
            tech_count = len(technologies)

        # 3. Get active finding counts
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

        # 4. Calculate score and build reasons
        score = 0
        reasons = []

        ext_weight = CRITICALITY_FACTORS["external_asset"]
        int_weight = CRITICALITY_FACTORS["internal_asset"]
        crit_find_weight = CRITICALITY_FACTORS["critical_finding"]
        high_find_weight = CRITICALITY_FACTORS["high_finding"]
        med_find_weight = CRITICALITY_FACTORS["medium_finding"]
        svc_weight = CRITICALITY_FACTORS["service_weight"]
        tech_weight = CRITICALITY_FACTORS["technology_weight"]
        svc_cap = CRITICALITY_FACTORS["service_cap"]
        tech_cap = CRITICALITY_FACTORS["technology_cap"]

        if exposure == ExposureClassification.EXTERNAL:
            score += ext_weight
            reasons.append(f"Asset is internet-exposed (+{ext_weight})")
        elif exposure == ExposureClassification.INTERNAL:
            score += int_weight
            reasons.append(f"Asset is internally exposed (+{int_weight})")

        crit_find = finding_counts.get("critical", 0)
        high_find = finding_counts.get("high", 0)
        med_find = finding_counts.get("medium", 0)

        if crit_find > 0:
            score += crit_find_weight
            reasons.append(
                f"Asset has {crit_find} critical finding(s) (+{crit_find_weight})"
            )
        elif high_find > 0:
            score += high_find_weight
            reasons.append(
                f"Asset has {high_find} high finding(s) (+{high_find_weight})"
            )
        elif med_find > 0:
            score += med_find_weight
            reasons.append(
                f"Asset has {med_find} medium finding(s) (+{med_find_weight})"
            )

        if service_count > 0:
            svc_contrib = min(svc_cap, service_count * svc_weight)
            score += svc_contrib
            reasons.append(f"Asset runs {service_count} service(s) (+{svc_contrib})")

        if tech_count > 0:
            tech_contrib = min(tech_cap, tech_count * tech_weight)
            score += tech_contrib
            reasons.append(
                f"Asset runs {tech_count} technology/product(s) (+{tech_contrib})"
            )

        # Clamp score between 0 and 100
        score = min(max(score, 0), 100)

        # Map to level
        if score <= 24:
            criticality = AssetCriticality.LOW
        elif score <= 49:
            criticality = AssetCriticality.MEDIUM
        elif score <= 74:
            criticality = AssetCriticality.HIGH
        else:
            criticality = AssetCriticality.CRITICAL

        return {
            "criticality": criticality,
            "score": score,
            "reasons": reasons,
        }
