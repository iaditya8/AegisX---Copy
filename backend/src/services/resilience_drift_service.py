import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.workflow_event_service import WorkflowEventService
from src.services.cyber_resilience_snapshot_service import CyberResilienceSnapshotService


class ResilienceDriftService:
    @classmethod
    async def check_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Compare current resilience values against baseline snapshots to identify regressions."""
        if not prev_snapshot or "summary" not in prev_snapshot:
            return

        curr_snap = await CyberResilienceSnapshotService.generate_snapshot(db, scope_id)
        prev_summary = prev_snapshot["summary"]

        curr_res = curr_snap["summary"]["resilience_score"]
        prev_res = prev_summary.get("resilience_score", 100.0)
        if curr_res != prev_res:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="resilience.drift",
                payload={
                    "drift_type": "RESILIENCE_SCORE_CHANGED",
                    "previous": prev_res,
                    "current": curr_res,
                },
            )

        curr_read = curr_snap["summary"]["readiness_score"]
        prev_read = prev_summary.get("readiness_score", 100.0)
        if curr_read < prev_read:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="resilience.drift",
                payload={
                    "drift_type": "READINESS_DECREASED",
                    "previous": prev_read,
                    "current": curr_read,
                },
            )
        elif curr_read > prev_read:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="resilience.drift",
                payload={
                    "drift_type": "READINESS_INCREASED",
                    "previous": prev_read,
                    "current": curr_read,
                },
            )

        curr_conf = curr_snap["summary"]["recovery_confidence_score"]
        prev_conf = prev_summary.get("recovery_confidence_score", 100.0)
        if curr_conf != prev_conf:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="resilience.drift",
                payload={
                    "drift_type": "RECOVERY_CONFIDENCE_CHANGED",
                    "previous": prev_conf,
                    "current": curr_conf,
                },
            )

        curr_comp = curr_snap["summary"]["objective_compliance"]
        prev_comp = prev_summary.get("objective_compliance", 100.0)
        if curr_comp != prev_comp:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="resilience.drift",
                payload={
                    "drift_type": "OBJECTIVE_COMPLIANCE_CHANGED",
                    "previous": prev_comp,
                    "current": curr_comp,
                },
            )
