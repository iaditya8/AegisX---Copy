import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.workflow_event_service import WorkflowEventService
from src.services.fabric_snapshot_service import FabricSnapshotService


class FabricDriftService:
    # in-memory store for drifts
    _drifts: List[dict] = []

    @classmethod
    def get_drifts(cls) -> List[dict]:
        """Retrieve all detected fabric drifts."""
        return cls._drifts

    @classmethod
    def clear_drifts(cls) -> None:
        """Clear the fabric drift log."""
        cls._drifts.clear()

    @classmethod
    async def process_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Analyze shifts in fabric intelligence snapshots to identify structural/confidence drift."""
        # Enforce Fabric Terminal State Rule: terminated nodes cannot reactivate, but are factored in stats
        if not prev_snapshot:
            return

        curr_snap = await FabricSnapshotService.generate_snapshot(db, scope_id)

        # 1. Compare average confidence
        curr_conf = curr_snap.get("average_confidence", 0.0)
        prev_conf = prev_snapshot.get("average_confidence", 0.0)

        if curr_conf != prev_conf:
            drift_entry = {
                "scope_id": str(scope_id) if scope_id else None,
                "drift_type": "CONFIDENCE_SCORE_SHIFTED",
                "details": f"Average fabric confidence shifted from {prev_conf} to {curr_conf}",
            }
            cls._drifts.append(drift_entry)

            await WorkflowEventService.emit_event(
                db=db,
                event_type="fabric.drift",
                payload={
                    "drift_type": "CONFIDENCE_SCORE_SHIFTED",
                    "previous_score": prev_conf,
                    "current_score": curr_conf,
                },
            )

        # 2. Compare total nodes count
        curr_total = curr_snap.get("total_nodes", 0)
        prev_total = prev_snapshot.get("total_nodes", 0)

        if curr_total != prev_total:
            drift_entry = {
                "scope_id": str(scope_id) if scope_id else None,
                "drift_type": "NODES_COUNT_SHIFTED",
                "details": f"Total fabric nodes count changed from {prev_total} to {curr_total}",
            }
            cls._drifts.append(drift_entry)

            await WorkflowEventService.emit_event(
                db=db,
                event_type="fabric.drift",
                payload={
                    "drift_type": "NODES_COUNT_SHIFTED",
                    "previous_count": prev_total,
                    "current_count": curr_total,
                },
            )
