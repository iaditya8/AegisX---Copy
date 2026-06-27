import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.workflow_event_service import WorkflowEventService
from src.services.soc_snapshot_service import SOCSnapshotService


class SOCDriftService:
    @classmethod
    async def process_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Compare current SOC metrics against prior snapshot baseline to detect performance drift."""
        if not prev_snapshot or "summary" not in prev_snapshot:
            return

        curr_snap = await SOCSnapshotService.generate_snapshot(db, scope_id)
        curr_sum = curr_snap["summary"]
        prev_sum = prev_snapshot["summary"]

        curr_health = curr_sum.get("operational_health_score", 100.0)
        prev_health = prev_sum.get("operational_health_score", 100.0)

        if curr_health < prev_health:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="soc.drift",
                payload={
                    "drift_type": "PERFORMANCE_DEGRADED",
                    "previous_health": prev_health,
                    "current_health": curr_health,
                },
            )
        elif curr_health > prev_health:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="soc.drift",
                payload={
                    "drift_type": "PERFORMANCE_IMPROVED",
                    "previous_health": prev_health,
                    "current_health": curr_health,
                },
            )

        # Check for change in queue efficiency
        curr_eff = curr_sum.get("queue_efficiency", 100.0)
        prev_eff = prev_sum.get("queue_efficiency", 100.0)
        if curr_eff != prev_eff:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="soc.performance_changed",
                payload={
                    "metric": "queue_efficiency",
                    "previous": prev_eff,
                    "current": curr_eff,
                },
            )
