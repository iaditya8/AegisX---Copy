import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.services.detection_coverage_service import DetectionCoverageService
from src.services.detection_snapshot_service import DetectionSnapshotService
from src.services.workflow_event_service import WorkflowEventService


class DetectionDriftService:
    @classmethod
    async def check_drift(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None, prev_snapshot: Optional[dict] = None
    ) -> None:
        """Check for overall coverage score decreases or ATT&CK technique mapping changes, emitting detection.drift events."""
        if prev_snapshot is None:
            prev_snapshot = DetectionSnapshotService._snapshots.get(scope_id)

        if not prev_snapshot:
            # No baseline to check drift against
            return

        # Calculate current coverage metrics
        coverage = DetectionCoverageService.calculate_coverage(scope_id)
        current_score = DetectionCoverageService.calculate_overall_score(scope_id)

        # 1. Compare overall score
        prev_score = prev_snapshot.get("coverage_score", 0.0)
        if current_score < prev_score:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="detection.drift",
                correlation_id=scope_id,
                payload={
                    "type": "score_decreased",
                    "previous_score": prev_score,
                    "current_score": current_score,
                    "scope_id": str(scope_id) if scope_id else None,
                },
            )

        # 2. Compare technique-level statuses and counts (mapping changes)
        for item in coverage:
            prev_tech = prev_snapshot.get("techniques", {}).get(item.technique_id)
            if prev_tech:
                prev_status = prev_tech.get("coverage_status")
                prev_count = prev_tech.get("detection_count")
                curr_status = item.coverage_status.value
                curr_count = item.detection_count

                if prev_status != curr_status or prev_count != curr_count:
                    await WorkflowEventService.emit_event(
                        db=db,
                        event_type="detection.drift",
                        correlation_id=scope_id,
                        payload={
                            "type": "mapping_changed",
                            "technique_id": item.technique_id,
                            "previous_status": prev_status,
                            "current_status": curr_status,
                            "previous_count": prev_count,
                            "current_count": curr_count,
                            "scope_id": str(scope_id) if scope_id else None,
                        },
                    )
