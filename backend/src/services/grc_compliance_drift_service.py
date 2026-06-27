import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.workflow_event_service import WorkflowEventService
from src.services.compliance_snapshot_service import ComplianceSnapshotService


class GRCComplianceDriftService:
    @classmethod
    async def process_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Compare GRC compliance parameters against baseline snapshot to detect drift."""
        if not prev_snapshot or "summary" not in prev_snapshot:
            return

        curr_snap = await ComplianceSnapshotService.generate_snapshot(db, scope_id)
        curr_sum = curr_snap["summary"]
        prev_sum = prev_snapshot["summary"]

        curr_score = curr_sum.get("average_compliance_score", 0.0)
        prev_score = prev_sum.get("average_compliance_score", 0.0)

        if curr_score < prev_score:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="compliance.drift",
                payload={
                    "drift_type": "COMPLIANCE_DECREASED",
                    "previous_score": prev_score,
                    "current_score": curr_score,
                },
            )
        elif curr_score > prev_score:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="compliance.drift",
                payload={
                    "drift_type": "COMPLIANCE_INCREASED",
                    "previous_score": prev_score,
                    "current_score": curr_score,
                },
            )

        if curr_score != prev_score:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="compliance.score_changed",
                payload={
                    "previous": prev_score,
                    "current": curr_score,
                },
            )
