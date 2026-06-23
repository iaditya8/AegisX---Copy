import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import (
    Asset,
    AssetPort,
    AssetService,
    Finding,
    WorkflowEvent,
)
from src.services.asset_risk_snapshot_service import AssetRiskSnapshotService


class DashboardService:
    """Service to aggregate platform-wide statistics dynamically with caching."""

    _cache: Optional[Dict[str, Any]] = None
    _cache_timestamp: Optional[datetime] = None

    @classmethod
    async def refresh_cache(
        cls,
        db: AsyncSession,
        scan_run_id: Optional[uuid.UUID] = None,
        workflow_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Compute the dashboard statistics dynamically, update the in-memory cache,

        and emit a dashboard.updated workflow event if workflow context is provided.
        """
        # 1. Total active assets count
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        res_assets = await db.execute(q_assets)
        assets = res_assets.scalars().all()
        asset_count = len(assets)

        # 2. Get asset risk snapshots to compute exposure and risk distribution
        internet_exposed_assets = 0
        risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        for asset in assets:
            snapshot = AssetRiskSnapshotService.get_snapshot(asset.id)
            # Generate snapshot on the fly if it is empty/default
            if (
                snapshot.get("exposure") == "UNKNOWN"
                and snapshot.get("risk_score") == 0
            ):
                snapshot = await AssetRiskSnapshotService.generate_snapshot(
                    db, asset.id
                )

            exposure_val = snapshot.get("exposure", "UNKNOWN")
            if exposure_val == "EXTERNAL":
                internet_exposed_assets += 1

            risk_level = str(snapshot.get("risk_level", "LOW")).lower()
            if risk_level in risk_counts:
                risk_counts[risk_level] += 1

        # 3. Total open ports count
        q_ports = (
            select(func.count(AssetPort.id))
            .join(Asset)
            .where(Asset.deleted_at.is_(None), AssetPort.state == "open")
        )
        res_ports = await db.execute(q_ports)
        open_ports = res_ports.scalar() or 0

        # 4. Total services count
        q_services = (
            select(func.count(AssetService.id))
            .join(AssetPort)
            .join(Asset)
            .where(Asset.deleted_at.is_(None), AssetPort.state == "open")
        )
        res_services = await db.execute(q_services)
        services = res_services.scalar() or 0

        # 5. Total findings by severity (counting open and acknowledged findings)
        q_findings = (
            select(Finding.severity, func.count(Finding.id))
            .join(Asset)
            .where(
                Asset.deleted_at.is_(None),
                Finding.status.in_(["open", "acknowledged"]),
            )
            .group_by(Finding.severity)
        )
        res_findings = await db.execute(q_findings)
        finding_rows = res_findings.all()

        findings_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for severity, count in finding_rows:
            sev_lower = str(severity).lower()
            if sev_lower in findings_counts:
                findings_counts[sev_lower] = count

        stats = {
            "asset_count": asset_count,
            "internet_exposed_assets": internet_exposed_assets,
            "open_ports": open_ports,
            "services": services,
            "findings": findings_counts,
            "risk": risk_counts,
        }

        cls._cache = stats
        cls._cache_timestamp = datetime.now(timezone.utc)

        # Emit workflow event if context is provided
        if workflow_id:
            event_id = uuid.uuid4()
            now = datetime.now(timezone.utc)
            event = WorkflowEvent(
                id=event_id,
                workflow_id=workflow_id,
                event_type="dashboard.updated",
                correlation_id=scan_run_id,
                payload={
                    "event_id": str(event_id),
                    "correlation_id": str(scan_run_id) if scan_run_id else None,
                    "workflow_id": str(workflow_id),
                    "scan_run_id": str(scan_run_id) if scan_run_id else None,
                    "timestamp": now.isoformat(),
                    "stats": stats,
                },
                timestamp=now,
            )
            db.add(event)
            await db.commit()

        return stats

    @classmethod
    async def get_dashboard_summary(
        cls, db: AsyncSession, bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """Get the cached dashboard statistics, or compute them if not cached."""
        if bypass_cache or cls._cache is None:
            return await cls.refresh_cache(db)
        return cls._cache

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the cache (primarily for tests)."""
        cls._cache = None
        cls._cache_timestamp = None
