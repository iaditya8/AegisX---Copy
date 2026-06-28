import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.workflow_event_service import WorkflowEventService
from src.services.planning_snapshot_service import PlanningSnapshotService


from src.infrastructure.cache.cache_dict import CacheList


class PlanningDriftService:
    # in-memory store for drifts
    _drifts = CacheList("planning_drifts")

    @classmethod
    def get_drifts(cls) -> List[dict]:
        """Retrieve all detected planning drifts."""
        return cls._drifts

    @classmethod
    def clear_drifts(cls) -> None:
        """Clear the planning drift log."""
        cls._drifts.clear()

    @classmethod
    async def process_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Analyze shifts in planning intelligence snapshots to identify structural drift or delays."""
        # Enforce Planning Terminal State Rule: closed plans cannot reactivate, but they are factored in stats
        if not prev_snapshot:
            return

        curr_snap = await PlanningSnapshotService.generate_snapshot(db, scope_id)

        # 1. Compare average progress
        curr_progress = curr_snap.get("average_progress", 0.0)
        prev_progress = prev_snapshot.get("average_progress", 0.0)

        if curr_progress != prev_progress:
            drift_entry = {
                "scope_id": str(scope_id) if scope_id else None,
                "drift_type": "PROGRESS_SCORE_SHIFTED",
                "details": f"Average plan progress shifted from {prev_progress} to {curr_progress}",
            }
            cls._drifts.append(drift_entry)

            await WorkflowEventService.emit_event(
                db=db,
                event_type="planning.drift",
                payload={
                    "drift_type": "PROGRESS_SCORE_SHIFTED",
                    "previous_score": prev_progress,
                    "current_score": curr_progress,
                },
            )

        # 2. Compare total plans count
        curr_total = curr_snap.get("total_plans", 0)
        prev_total = prev_snapshot.get("total_plans", 0)

        if curr_total != prev_total:
            drift_entry = {
                "scope_id": str(scope_id) if scope_id else None,
                "drift_type": "PLANS_COUNT_SHIFTED",
                "details": f"Total plans count changed from {prev_total} to {curr_total}",
            }
            cls._drifts.append(drift_entry)

            await WorkflowEventService.emit_event(
                db=db,
                event_type="planning.drift",
                payload={
                    "drift_type": "PLANS_COUNT_SHIFTED",
                    "previous_count": prev_total,
                    "current_count": curr_total,
                },
            )

        # 3. Compare active or approved counts
        curr_act = curr_snap.get("active_count", 0)
        prev_act = prev_snapshot.get("active_count", 0)
        curr_app = curr_snap.get("approved_count", 0)
        prev_app = prev_snapshot.get("approved_count", 0)

        if curr_act != prev_act or curr_app != prev_app:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="planning.milestone_changed",
                payload={
                    "previous_approved": prev_app,
                    "current_approved": curr_app,
                    "previous_active": prev_act,
                    "current_active": curr_act,
                },
            )
