import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.detection import CoverageStatus
from src.services.detection_coverage_service import DetectionCoverageService
from src.services.detection_snapshot_service import DetectionSnapshotService
from src.services.workflow_event_service import WorkflowEventService


class DetectionGapService:
    @classmethod
    async def check_gaps_and_regressions(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None, prev_snapshot: Optional[dict] = None
    ) -> None:
        """Analyze coverage gaps and regressions, emitting corresponding events."""
        if prev_snapshot is None:
            prev_snapshot = DetectionSnapshotService._snapshots.get(scope_id)

        # Calculate current coverage metrics
        coverage = DetectionCoverageService.calculate_coverage(scope_id)
        current_score = DetectionCoverageService.calculate_overall_score(scope_id)

        # 1. Identify gaps (NOT_COVERED)
        for item in coverage:
            if item.coverage_status == CoverageStatus.NOT_COVERED:
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="detection.gap_detected",
                    correlation_id=scope_id,
                    payload={
                        "technique_id": item.technique_id,
                        "scope_id": str(scope_id) if scope_id else None,
                        "status": item.coverage_status.value,
                    },
                )

            # 2. Check for technique-level regressions if previous snapshot exists
            if prev_snapshot:
                prev_tech = prev_snapshot.get("techniques", {}).get(item.technique_id)
                if prev_tech:
                    prev_status = prev_tech.get("coverage_status")
                    curr_status = item.coverage_status.value
                    if prev_status == "COVERED" and curr_status in ["PARTIALLY_COVERED", "NOT_COVERED"]:
                        await WorkflowEventService.emit_event(
                            db=db,
                            event_type="detection.coverage_regressed",
                            correlation_id=scope_id,
                            payload={
                                "technique_id": item.technique_id,
                                "previous_status": prev_status,
                                "current_status": curr_status,
                                "scope_id": str(scope_id) if scope_id else None,
                            },
                        )

        # 3. Check for score-level regression
        if prev_snapshot:
            prev_score = prev_snapshot.get("coverage_score", 0.0)
            if current_score < prev_score:
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="detection.coverage_regressed",
                    correlation_id=scope_id,
                    payload={
                        "previous_score": prev_score,
                        "current_score": current_score,
                        "scope_id": str(scope_id) if scope_id else None,
                        "details": "Overall detection coverage score decreased.",
                    },
                )

