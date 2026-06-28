import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.workflow_event_service import WorkflowEventService
from src.services.decision_snapshot_service import DecisionSnapshotService


from src.infrastructure.cache.cache_dict import CacheList


class DecisionDriftService:
    # in-memory store for drifts
    _drifts = CacheList("decision_drifts")

    @classmethod
    def get_drifts(cls) -> List[dict]:
        """Retrieve all detected decision drifts."""
        return cls._drifts

    @classmethod
    def clear_drifts(cls) -> None:
        """Clear the decision drift log."""
        cls._drifts.clear()

    @classmethod
    async def process_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Analyze changes in decision intelligence snapshots to identify structural/tradeoff drift."""
        # Enforce Decision Terminal State Rule: archived decisions cannot reactivate, but they are factored in stats
        if not prev_snapshot:
            return

        curr_snap = await DecisionSnapshotService.generate_snapshot(db, scope_id)

        # 1. Compare average net benefit
        curr_benefit = curr_snap.get("average_net_benefit", 0.0)
        prev_benefit = prev_snapshot.get("average_net_benefit", 0.0)

        if curr_benefit != prev_benefit:
            drift_entry = {
                "scope_id": str(scope_id) if scope_id else None,
                "drift_type": "BENEFIT_SCORE_SHIFTED",
                "details": f"Average net benefit shifted from {prev_benefit} to {curr_benefit}",
            }
            cls._drifts.append(drift_entry)

            await WorkflowEventService.emit_event(
                db=db,
                event_type="decision.drift",
                payload={
                    "drift_type": "BENEFIT_SCORE_SHIFTED",
                    "previous_score": prev_benefit,
                    "current_score": curr_benefit,
                },
            )

        # 2. Compare total decisions count
        curr_total = curr_snap.get("total_decisions", 0)
        prev_total = prev_snapshot.get("total_decisions", 0)

        if curr_total != prev_total:
            drift_entry = {
                "scope_id": str(scope_id) if scope_id else None,
                "drift_type": "DECISIONS_COUNT_SHIFTED",
                "details": f"Total decisions count changed from {prev_total} to {curr_total}",
            }
            cls._drifts.append(drift_entry)

            await WorkflowEventService.emit_event(
                db=db,
                event_type="decision.drift",
                payload={
                    "drift_type": "DECISIONS_COUNT_SHIFTED",
                    "previous_count": prev_total,
                    "current_count": curr_total,
                },
            )

        # 3. Compare committed or recommended status counts
        curr_com = curr_snap.get("committed_count", 0)
        prev_com = prev_snapshot.get("committed_count", 0)
        curr_rec = curr_snap.get("recommended_count", 0)
        prev_rec = prev_snapshot.get("recommended_count", 0)

        if curr_com != prev_com or curr_rec != prev_rec:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="decision.status_changed",
                payload={
                    "previous_recommended": prev_rec,
                    "current_recommended": curr_rec,
                    "previous_committed": prev_com,
                    "current_committed": curr_com,
                },
            )
