import uuid
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Asset, AssetPort, AssetService, Finding
from src.services.asset_risk_snapshot_service import AssetRiskSnapshotService
from src.services.correlation_snapshot_service import CorrelationSnapshotService


class AssetReportService:
    """Service to compile detailed report for a single asset."""

    _cache: Dict[uuid.UUID, Dict[str, Any]] = {}

    @classmethod
    async def generate_asset_report(
        cls, db: AsyncSession, asset_id: uuid.UUID, bypass_cache: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Consolidate asset details, exposure, risk, ports, services,
        technologies, and findings. Returns None if not found or deleted.
        """
        if not bypass_cache and asset_id in cls._cache:
            return cls._cache[asset_id]
        # 1. Fetch asset
        asset = await db.get(Asset, asset_id)
        if not asset or asset.deleted_at is not None:
            return None

        # 2. Get correlation snapshot (for exposure, products, technologies)
        corr_snapshot = CorrelationSnapshotService.get_snapshot(asset_id)
        if corr_snapshot.get("exposure") == "UNKNOWN" and not corr_snapshot.get(
            "ports"
        ):
            corr_snapshot = await CorrelationSnapshotService.generate_snapshot(
                db, asset_id
            )

        # 3. Get risk snapshot
        risk_snapshot = AssetRiskSnapshotService.get_snapshot(asset_id)
        if (
            risk_snapshot.get("exposure") == "UNKNOWN"
            and risk_snapshot.get("risk_score") == 0
        ):
            risk_snapshot = await AssetRiskSnapshotService.generate_snapshot(
                db, asset_id
            )

        # 4. Fetch open ports
        q_ports = select(AssetPort).where(
            AssetPort.asset_id == asset_id, AssetPort.state == "open"
        )
        res_ports = await db.execute(q_ports)
        ports = res_ports.scalars().all()

        ports_list = [
            {
                "id": str(p.id),
                "port": p.port,
                "protocol": p.protocol,
                "state": p.state,
                "first_seen": p.first_seen.isoformat() if p.first_seen else None,
                "last_seen": p.last_seen.isoformat() if p.last_seen else None,
            }
            for p in ports
        ]

        # 5. Fetch services
        q_services = (
            select(AssetService, AssetPort.port)
            .join(AssetPort)
            .where(AssetPort.asset_id == asset_id, AssetPort.state == "open")
        )
        res_services = await db.execute(q_services)
        services_rows = res_services.all()

        services_list = [
            {
                "id": str(s.id),
                "port": port,
                "service_name": s.service_name,
                "product": s.product,
                "version": s.version,
                "banner": s.banner,
                "confidence": float(s.confidence),
            }
            for s, port in services_rows
        ]

        # 6. Fetch active findings (open or acknowledged)
        q_findings = select(Finding).where(
            Finding.asset_id == asset_id, Finding.status.in_(["open", "acknowledged"])
        )
        res_findings = await db.execute(q_findings)
        findings = res_findings.scalars().all()

        findings_list = [
            {
                "id": str(f.id),
                "title": f.title,
                "description": f.description,
                "severity": f.severity,
                "status": f.status,
                "template_id": f.template_id,
                "template_name": f.template_name,
                "source_plugin": f.source_plugin,
                "first_seen": f.first_seen.isoformat() if f.first_seen else None,
                "last_seen": f.last_seen.isoformat() if f.last_seen else None,
                "metadata_json": f.metadata_json,
            }
            for f in findings
        ]

        asset_data = {
            "id": str(asset.id),
            "scope_id": str(asset.scope_id) if asset.scope_id else None,
            "host": asset.host,
            "ip": asset.ip,
            "asset_type": asset.asset_type,
            "first_seen": asset.first_seen.isoformat() if asset.first_seen else None,
            "last_seen": asset.last_seen.isoformat() if asset.last_seen else None,
            "fingerprint": asset.fingerprint,
        }

        # Structure response
        report = {
            "asset": asset_data,
            "exposure": {
                "classification": corr_snapshot.get("exposure", "UNKNOWN"),
                "risk_factors": corr_snapshot.get("risk_factors", []),
            },
            "risk": {
                "criticality": risk_snapshot.get("criticality", "LOW"),
                "risk_score": risk_snapshot.get("risk_score", 0),
                "risk_level": risk_snapshot.get("risk_level", "LOW"),
                "explanations": risk_snapshot.get("explanations", []),
            },
            "ports": ports_list,
            "services": services_list,
            "technologies": corr_snapshot.get("technologies", []),
            "findings": findings_list,
        }

        cls._cache[asset_id] = report
        return report
