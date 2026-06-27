import uuid
from typing import Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.executive_reporting import ExecutiveReportStatus
from src.services.executive_reporting_service import ExecutiveReportingService
from src.services.executive_scorecard_service import ExecutiveScorecardService
from src.services.executive_heatmap_service import ExecutiveHeatmapService
from src.services.executive_trend_service import ExecutiveTrendService


class ExecutiveSnapshotService:
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
                    "total_reports": 0,
                    "draft_reports_count": 0,
                    "published_reports_count": 0,
                    "archived_reports_count": 0,
                    "overall_health_score": 100.0,
                },
                "scorecard": {},
                "heatmap": {},
                "trends": {},
                "reports": {},
            }
        return snap

    @classmethod
    async def generate_snapshot(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None
    ) -> dict:
        """Dynamically rebuild snapshot stats from active report records."""
        all_reports = ExecutiveReportingService.get_all_reports()
        if scope_id:
            all_reports = [r for r in all_reports if r.scope_id == scope_id]

        total_reports = len(all_reports)
        draft_count = sum(1 for r in all_reports if r.status == ExecutiveReportStatus.DRAFT)
        pub_count = sum(1 for r in all_reports if r.status == ExecutiveReportStatus.PUBLISHED)
        arch_count = sum(1 for r in all_reports if r.status == ExecutiveReportStatus.ARCHIVED)

        # Calculate scorecard, heatmap, trends
        scorecard = ExecutiveScorecardService.calculate_scorecard(scope_id)
        heatmap = ExecutiveHeatmapService.generate_heatmap(scope_id)
        trends = ExecutiveTrendService.get_trends(scope_id)

        reports_track = {}
        for r in all_reports:
            reports_track[str(r.report_id)] = {
                "report_id": str(r.report_id),
                "title": r.title,
                "status": r.status.value,
                "overall_risk_score": r.overall_risk_score,
                "program_score": r.program_score,
                "scorecard_status": r.scorecard_status.value,
            }

        snapshot = {
            "summary": {
                "total_reports": total_reports,
                "draft_reports_count": draft_count,
                "published_reports_count": pub_count,
                "archived_reports_count": arch_count,
                "overall_health_score": scorecard.overall_health,
            },
            "scorecard": {
                "scorecard_id": str(scorecard.scorecard_id),
                "overall_health": scorecard.overall_health,
                "risk_score": scorecard.risk_score,
                "program_score": scorecard.program_score,
                "kpi_score": scorecard.kpi_score,
                "kri_score": scorecard.kri_score,
                "coverage_score": scorecard.coverage_score,
                "trend_score": scorecard.trend_score,
            },
            "heatmap": heatmap,
            "trends": trends,
            "reports": reports_track,
        }

        cls._snapshots[scope_id] = snapshot
        return snapshot
