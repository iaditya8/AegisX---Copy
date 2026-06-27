import uuid
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.security_posture_service import SecurityPostureService
from src.services.workflow_event_service import WorkflowEventService


class PostureDriftService:
    @classmethod
    async def check_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Compare current posture scores against baseline to detect posture shifts or risk alerts."""
        if not prev_snapshot or "summary" not in prev_snapshot:
            return

        from src.services.security_posture_snapshot_service import SecurityPostureSnapshotService
        
        # Build current snapshot details dynamically
        curr_snap = await SecurityPostureSnapshotService.generate_snapshot(db, scope_id)

        curr_summary = curr_snap["summary"]
        prev_summary = prev_snapshot["summary"]

        # 1. RISK_INCREASED / RISK_DECREASED
        curr_risk = curr_summary.get("organizational_risk_score", 0.0)
        prev_risk = prev_summary.get("organizational_risk_score", 0.0)
        if curr_risk > prev_risk:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="security_posture.drift",
                payload={
                    "drift_type": "RISK_INCREASED",
                    "previous_risk_score": prev_risk,
                    "current_risk_score": curr_risk,
                },
            )
        elif curr_risk < prev_risk:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="security_posture.drift",
                payload={
                    "drift_type": "RISK_DECREASED",
                    "previous_risk_score": prev_risk,
                    "current_risk_score": curr_risk,
                },
            )

        # 2. POSTURE_CHANGED
        curr_posture = curr_summary.get("security_posture_score", 100.0)
        prev_posture = prev_summary.get("security_posture_score", 100.0)
        if curr_posture != prev_posture:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="security_posture.drift",
                payload={
                    "drift_type": "POSTURE_CHANGED",
                    "previous_posture_score": prev_posture,
                    "current_posture_score": curr_posture,
                },
            )

        # 3. EXPOSURE_INCREASED / EXPOSURE_DECREASED
        curr_crit = curr_summary.get("critical_risk_count", 0)
        prev_crit = prev_summary.get("critical_risk_count", 0)
        if curr_crit > prev_crit:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="security_posture.drift",
                payload={
                    "drift_type": "EXPOSURE_INCREASED",
                    "previous_critical_risk_count": prev_crit,
                    "current_critical_risk_count": curr_crit,
                },
            )
        elif curr_crit < prev_crit:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="security_posture.drift",
                payload={
                    "drift_type": "EXPOSURE_DECREASED",
                    "previous_critical_risk_count": prev_crit,
                    "current_critical_risk_count": curr_crit,
                },
            )

        # 4. COVERAGE_CHANGED
        curr_cov = curr_summary.get("attack_surface_coverage", 100.0)
        prev_cov = prev_summary.get("attack_surface_coverage", 100.0)
        if curr_cov != prev_cov:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="security_posture.drift",
                payload={
                    "drift_type": "COVERAGE_CHANGED",
                    "previous_coverage": prev_cov,
                    "current_coverage": curr_cov,
                },
            )
Definition = """
RISK_INCREASED, RISK_DECREASED, POSTURE_CHANGED, EXPOSURE_INCREASED, EXPOSURE_DECREASED, COVERAGE_CHANGED
"""
