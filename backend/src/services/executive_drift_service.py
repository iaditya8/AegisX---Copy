import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.workflow_event_service import WorkflowEventService
from src.services.executive_scorecard_service import ExecutiveScorecardService


class ExecutiveDriftService:
    @classmethod
    async def check_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Compare current scorecard values against baseline snapshots to identify regressions."""
        if not prev_snapshot or "scorecard" not in prev_snapshot:
            return

        curr_scorecard = ExecutiveScorecardService.calculate_scorecard(scope_id)
        prev_scorecard = prev_snapshot["scorecard"]

        # 1. Health decreased
        if curr_scorecard.overall_health < prev_scorecard.get("overall_health", 100.0):
            await WorkflowEventService.emit_event(
                db=db,
                event_type="executive.drift",
                payload={
                    "drift_type": "EXECUTIVE_HEALTH_DEGRADED",
                    "previous_health": prev_scorecard.get("overall_health"),
                    "current_health": curr_scorecard.overall_health,
                },
            )

        # 2. Risk score decreased (meaning risk grew higher)
        if curr_scorecard.risk_score < prev_scorecard.get("risk_score", 100.0):
            await WorkflowEventService.emit_event(
                db=db,
                event_type="executive.drift",
                payload={
                    "drift_type": "RISK_INCREASED",
                    "previous_risk": prev_scorecard.get("risk_score"),
                    "current_risk": curr_scorecard.risk_score,
                },
            )

        # 3. Indicator drifts
        if curr_scorecard.program_score != prev_scorecard.get("program_score", 100.0):
            await WorkflowEventService.emit_event(
                db=db,
                event_type="executive.drift",
                payload={
                    "drift_type": "PROGRAM_SCORE_CHANGED",
                    "previous": prev_scorecard.get("program_score"),
                    "current": curr_scorecard.program_score,
                },
            )

        if curr_scorecard.kpi_score != prev_scorecard.get("kpi_score", 100.0):
            await WorkflowEventService.emit_event(
                db=db,
                event_type="executive.drift",
                payload={
                    "drift_type": "KPI_CHANGED",
                    "previous": prev_scorecard.get("kpi_score"),
                    "current": curr_scorecard.kpi_score,
                },
            )

        if curr_scorecard.kri_score != prev_scorecard.get("kri_score", 100.0):
            await WorkflowEventService.emit_event(
                db=db,
                event_type="executive.drift",
                payload={
                    "drift_type": "KRI_CHANGED",
                    "previous": prev_scorecard.get("kri_score"),
                    "current": curr_scorecard.kri_score,
                },
            )

        if curr_scorecard.coverage_score != prev_scorecard.get("coverage_score", 100.0):
            await WorkflowEventService.emit_event(
                db=db,
                event_type="executive.drift",
                payload={
                    "drift_type": "COVERAGE_CHANGED",
                    "previous": prev_scorecard.get("coverage_score"),
                    "current": curr_scorecard.coverage_score,
                },
            )
