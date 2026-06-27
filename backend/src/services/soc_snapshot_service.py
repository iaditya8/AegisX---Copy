import uuid
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.analyst_performance_service import AnalystPerformanceService
from src.services.queue_analytics_service import QueueAnalyticsService
from src.services.operational_kpi_service import OperationalKPIService
from src.services.operational_kri_service import OperationalKRIService


class SOCSnapshotService:
    # Cache store: scope_id -> Snapshot dictionary
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear the snapshot cache."""
        cls._snapshots.clear()

    @classmethod
    def get_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Retrieve the cached snapshot, defaulting to a minimal fallback if missing or corrupted."""
        snap = cls._snapshots.get(scope_id)
        if not snap or not isinstance(snap, dict) or "summary" not in snap:
            return {
                "summary": {
                    "total_analytics_records": 0,
                    "active_analytics_records": 0,
                    "completed_analytics_records": 0,
                    "operational_health_score": 100.0,
                    "queue_size": 0,
                    "queue_efficiency": 100.0,
                    "average_analyst_score": 100.0,
                },
                "analysts": {},
                "kpis": [],
                "kris": [],
            }
        return snap

    @classmethod
    async def generate_snapshot(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None
    ) -> dict:
        """Dynamically rebuild snapshot stats from SOC services."""
        from src.services.security_operations_analytics_service import SecurityOperationsAnalyticsService
        from src.domain.entities.security_operations_analytics import AnalyticsStatus

        all_recs = SecurityOperationsAnalyticsService.get_all_analytics()
        if scope_id:
            all_recs = [r for r in all_recs if r.scope_id == scope_id]

        total_recs = len(all_recs)
        active_count = sum(1 for r in all_recs if r.status == AnalyticsStatus.ACTIVE)
        comp_count = sum(
            1 for r in all_recs if r.status in (AnalyticsStatus.COMPLETED, AnalyticsStatus.ARCHIVED)
        )

        # Analyst summary stats
        analysts = AnalystPerformanceService.get_analysts()
        avg_score = (
            round(sum(a.analyst_score for a in analysts) / len(analysts), 2)
            if analysts
            else 100.0
        )

        # Queue efficiency
        q_summary = QueueAnalyticsService.get_queue_summary()

        # Operational health score is combination of average analyst performance + queue efficiency
        health_score = round(avg_score * 0.5 + q_summary["processing_efficiency"] * 0.5, 2)

        kpis = OperationalKPIService.get_kpis()
        kris = OperationalKRIService.get_kris()

        analysts_track = {
            str(a.analyst_id): {
                "analyst_name": a.analyst_name,
                "analyst_score": a.analyst_score,
                "alerts_handled": a.alerts_handled,
            }
            for a in analysts
        }

        snapshot = {
            "summary": {
                "total_analytics_records": total_recs,
                "active_analytics_records": active_count,
                "completed_analytics_records": comp_count,
                "operational_health_score": health_score,
                "queue_size": q_summary["queue_size"],
                "queue_efficiency": q_summary["processing_efficiency"],
                "average_analyst_score": avg_score,
            },
            "analysts": analysts_track,
            "kpis": [k.model_dump() for k in kpis],
            "kris": [k.model_dump() for k in kris],
        }

        cls._snapshots[scope_id] = snapshot
        return snapshot
