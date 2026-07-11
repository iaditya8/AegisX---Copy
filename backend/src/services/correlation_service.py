import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models import (
    CorrelationRule,
    CorrelationCluster,
    CorrelationHistory,
    Incident,
    Asset,
    AssetPort,
    AssetService,
    Finding,
)
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.services.correlation_incident_bridge import CorrelationIncidentBridge
from src.core.tenant import require_current_tenant_id
from src.services.asset_exposure_service import AssetExposureService, ExposureClassification


class CorrelationService:
    @classmethod
    async def create_rule(
        cls,
        name: str,
        description: Optional[str],
        condition_expression: dict,
        priority_level: str,
    ) -> CorrelationRule:
        tenant_id = require_current_tenant_id()
        async with UnitOfWork() as uow:
            rule = CorrelationRule(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name=name,
                description=description,
                condition_expression=condition_expression,
                priority_level=priority_level,
                rule_version=1,
            )
            await uow.correlation_repo.save_rule(rule)
            await uow.commit()
            return rule

    @classmethod
    async def list_rules(cls) -> List[CorrelationRule]:
        async with UnitOfWork() as uow:
            return await uow.correlation_repo.find_active_rules()

    @classmethod
    async def get_rule(cls, rule_id: uuid.UUID) -> Optional[CorrelationRule]:
        async with UnitOfWork() as uow:
            return await uow.correlation_repo.get_rule(rule_id)

    @classmethod
    async def list_clusters(cls) -> List[CorrelationCluster]:
        async with UnitOfWork() as uow:
            # We want to eagerly load the signals relationship
            tenant_id = require_current_tenant_id()
            query = select(CorrelationCluster).filter(
                CorrelationCluster.tenant_id == tenant_id
            ).options(
                selectinload(CorrelationCluster.signals),
                selectinload(CorrelationCluster.history)
            ).order_by(CorrelationCluster.unified_score.desc())
            res = await uow.session.execute(query)
            return list(res.scalars().all())

    @classmethod
    async def get_cluster(cls, cluster_id: uuid.UUID) -> Optional[CorrelationCluster]:
        async with UnitOfWork() as uow:
            tenant_id = require_current_tenant_id()
            query = select(CorrelationCluster).filter(
                CorrelationCluster.tenant_id == tenant_id,
                CorrelationCluster.id == cluster_id
            ).options(
                selectinload(CorrelationCluster.signals),
                selectinload(CorrelationCluster.history)
            )
            res = await uow.session.execute(query)
            return res.scalar_one_or_none()

    @classmethod
    async def get_history(cls, cluster_id: uuid.UUID) -> List[CorrelationHistory]:
        async with UnitOfWork() as uow:
            tenant_id = require_current_tenant_id()
            query = select(CorrelationHistory).filter(
                CorrelationHistory.tenant_id == tenant_id,
                CorrelationHistory.cluster_id == cluster_id
            ).order_by(CorrelationHistory.timestamp.asc())
            res = await uow.session.execute(query)
            return list(res.scalars().all())

    @classmethod
    async def escalate_cluster(
        cls,
        cluster_id: uuid.UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Incident:
        async with UnitOfWork() as uow:
            incident = await CorrelationIncidentBridge.escalate_cluster(
                db=uow.session,
                cluster_id=cluster_id,
                title=title,
                description=description,
            )
            await uow.commit()
            return incident

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
