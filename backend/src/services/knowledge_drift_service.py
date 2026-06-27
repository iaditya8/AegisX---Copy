import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.workflow_event_service import WorkflowEventService
from src.services.knowledge_snapshot_service import KnowledgeSnapshotService


class KnowledgeDriftService:
    @classmethod
    async def process_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Compare current GRC knowledge parameters against baseline snapshot to detect drift."""
        if not prev_snapshot or "summary" not in prev_snapshot:
            return

        curr_snap = await KnowledgeSnapshotService.generate_snapshot(db, scope_id)
        curr_sum = curr_snap["summary"]
        prev_sum = prev_snapshot["summary"]

        curr_relevance = curr_sum.get("average_relevance_score", 0.0)
        prev_relevance = prev_sum.get("average_relevance_score", 0.0)

        if curr_relevance < prev_relevance:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="knowledge.drift",
                payload={
                    "drift_type": "RELEVANCE_DECREASED",
                    "previous_score": prev_relevance,
                    "current_score": curr_relevance,
                },
            )
        elif curr_relevance > prev_relevance:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="knowledge.drift",
                payload={
                    "drift_type": "RELEVANCE_INCREASED",
                    "previous_score": prev_relevance,
                    "current_score": curr_relevance,
                },
            )

        if curr_relevance != prev_relevance:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="knowledge.score_changed",
                payload={
                    "previous": prev_relevance,
                    "current": curr_relevance,
                },
            )
        
        # Check for confidence drift
        curr_confidence = curr_sum.get("average_confidence_score", 0.0)
        prev_confidence = prev_sum.get("average_confidence_score", 0.0)
        if curr_confidence != prev_confidence:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="knowledge.drift",
                payload={
                    "drift_type": "CONFIDENCE_CHANGED",
                    "previous_score": prev_confidence,
                    "current_score": curr_confidence,
                },
            )
        
        # Check for recommendations drift
        curr_rec_count = curr_snap.get("records_count", 0)
        prev_rec_count = prev_snapshot.get("records_count", 0)
        if curr_rec_count != prev_rec_count:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="knowledge.drift",
                payload={
                    "drift_type": "RECOMMENDATIONS_CHANGED",
                    "previous_count": prev_rec_count,
                    "current_count": curr_rec_count,
                },
            )
