import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.workflow_event_service import WorkflowEventService
from src.services.threat_intel_snapshot_service import ThreatIntelSnapshotService


class ThreatIntelDriftService:
    @classmethod
    async def process_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Compare current GRC threat intelligence parameters against baseline snapshot to detect drift."""
        if not prev_snapshot or "summary" not in prev_snapshot:
            return

        curr_snap = await ThreatIntelSnapshotService.generate_snapshot(db, scope_id)
        curr_sum = curr_snap["summary"]
        prev_sum = prev_snapshot["summary"]

        curr_fusion = curr_sum.get("average_fusion_score", 0.0)
        prev_fusion = prev_sum.get("average_fusion_score", 0.0)

        if curr_fusion < prev_fusion:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="threat.drift",
                payload={
                    "drift_type": "FUSION_SCORE_DECREASED",
                    "previous_score": prev_fusion,
                    "current_score": curr_fusion,
                },
            )
        elif curr_fusion > prev_fusion:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="threat.drift",
                payload={
                    "drift_type": "FUSION_SCORE_INCREASED",
                    "previous_score": prev_fusion,
                    "current_score": curr_fusion,
                },
            )

        if curr_fusion != prev_fusion:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="threat.score_changed",
                payload={
                    "previous": prev_fusion,
                    "current": curr_fusion,
                },
            )
        
        # Check for count changes
        curr_total = curr_sum.get("total_threat_records", 0)
        prev_total = prev_sum.get("total_threat_records", 0)
        if curr_total != prev_total:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="threat.drift",
                payload={
                    "drift_type": "RECORDS_COUNT_CHANGED",
                    "previous_count": prev_total,
                    "current_count": curr_total,
                },
            )
