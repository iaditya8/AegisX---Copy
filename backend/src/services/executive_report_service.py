import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Asset, Finding, WorkflowEvent
from src.services.asset_risk_snapshot_service import AssetRiskSnapshotService
from src.services.dashboard_service import DashboardService


class ExecutiveReportService:
    """Service to generate deterministic executive reports with caching."""

    _cache: Optional[Dict[str, Any]] = None
    _cache_timestamp: Optional[datetime] = None

    @classmethod
    async def refresh_cache(
        cls,
        db: AsyncSession,
        scan_run_id: Optional[uuid.UUID] = None,
        workflow_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Generate a fresh executive report, cache it, and emit event."""
        # 1. Fetch dashboard summary to reuse stats for summary and risk_distribution
        summary_stats = await DashboardService.get_dashboard_summary(
            db, bypass_cache=True
        )

        # 2. Get all active assets
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        res_assets = await db.execute(q_assets)
        assets = res_assets.scalars().all()

        # 3. Compile asset details with risk snapshots
        asset_snapshots = []
        exposure_distribution = {"INTERNAL": 0, "EXTERNAL": 0, "UNKNOWN": 0}

        for asset in assets:
            snapshot = AssetRiskSnapshotService.get_snapshot(asset.id)
            if (
                snapshot.get("exposure") == "UNKNOWN"
                and snapshot.get("risk_score") == 0
            ):
                snapshot = await AssetRiskSnapshotService.generate_snapshot(
                    db, asset.id
                )

            exp = snapshot.get("exposure", "UNKNOWN")
            if exp in exposure_distribution:
                exposure_distribution[exp] += 1

            asset_snapshots.append(
                {
                    "id": str(asset.id),
                    "host": asset.host,
                    "ip": asset.ip,
                    "asset_type": asset.asset_type,
                    "risk_score": snapshot.get("risk_score", 0),
                    "risk_level": snapshot.get("risk_level", "LOW"),
                    "criticality": snapshot.get("criticality", "LOW"),
                    "exposure": exp,
                }
            )

        # Sort assets by risk score descending, take top 10
        top_risky_assets = sorted(
            asset_snapshots, key=lambda x: x["risk_score"], reverse=True
        )[:10]

        # 4. Fetch critical findings
        q_findings = (
            select(Finding)
            .join(Asset)
            .where(
                Asset.deleted_at.is_(None),
                Finding.severity == "critical",
                Finding.status.in_(["open", "acknowledged"]),
            )
            .order_by(Finding.created_at.desc())
            .limit(10)
        )
        res_findings = await db.execute(q_findings)
        findings = res_findings.scalars().all()

        critical_findings = [
            {
                "id": str(f.id),
                "asset_id": str(f.asset_id),
                "title": f.title,
                "severity": f.severity,
                "status": f.status,
                "template_id": f.template_id,
                "first_seen": f.first_seen.isoformat() if f.first_seen else None,
                "last_seen": f.last_seen.isoformat() if f.last_seen else None,
            }
            for f in findings
        ]

        report = {
            "summary": summary_stats,
            "top_risky_assets": top_risky_assets,
            "critical_findings": critical_findings,
            "risk_distribution": summary_stats["risk"],
            "exposure_distribution": exposure_distribution,
        }

        cls._cache = report
        cls._cache_timestamp = datetime.now(timezone.utc)

        # Emit report.generated event
        if workflow_id:
            event_id = uuid.uuid4()
            now = datetime.now(timezone.utc)
            event = WorkflowEvent(
                id=event_id,
                workflow_id=workflow_id,
                event_type="report.generated",
                correlation_id=scan_run_id,
                payload={
                    "event_id": str(event_id),
                    "correlation_id": str(scan_run_id) if scan_run_id else None,
                    "workflow_id": str(workflow_id),
                    "scan_run_id": str(scan_run_id) if scan_run_id else None,
                    "timestamp": now.isoformat(),
                    "report_type": "executive",
                },
                timestamp=now,
            )
            db.add(event)
            await db.commit()

        return report

    @classmethod
    async def get_executive_report(
        cls, db: AsyncSession, bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """Retrieve the cached executive report or compute it if not cached."""
        if bypass_cache or cls._cache is None:
            return await cls.refresh_cache(db)
        return cls._cache

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cache primarily for testing."""
        cls._cache = None
        cls._cache_timestamp = None
