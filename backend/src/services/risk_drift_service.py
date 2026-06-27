import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.workflow_event_service import WorkflowEventService
from src.services.risk_quantification_snapshot_service import RiskQuantificationSnapshotService


class RiskDriftService:
    @classmethod
    async def process_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Compare current risk quantification parameters against baseline to detect regressions."""
        if not prev_snapshot or "summary" not in prev_snapshot:
            return

        curr_snap = await RiskQuantificationSnapshotService.generate_snapshot(db, scope_id)
        curr_sum = curr_snap["summary"]
        prev_sum = prev_snapshot["summary"]

        curr_ale = curr_sum.get("total_annualized_loss_expectancy", 0.0)
        prev_ale = prev_sum.get("total_annualized_loss_expectancy", 0.0)

        if curr_ale > prev_ale:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="risk.drift",
                payload={
                    "drift_type": "EXPOSURE_INCREASED",
                    "previous_ale": prev_ale,
                    "current_ale": curr_ale,
                },
            )
        elif curr_ale < prev_ale:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="risk.drift",
                payload={
                    "drift_type": "EXPOSURE_DECREASED",
                    "previous_ale": prev_ale,
                    "current_ale": curr_ale,
                },
            )

        # Check for change in forecasts
        curr_forecast = curr_sum.get("projected_loss_forecast", 0.0)
        prev_forecast = prev_sum.get("projected_loss_forecast", 0.0)
        if curr_forecast != prev_forecast:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="risk.forecast_changed",
                payload={
                    "previous": prev_forecast,
                    "current": curr_forecast,
                },
            )
