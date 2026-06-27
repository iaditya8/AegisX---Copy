import uuid
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.control_validation_service import ControlValidationService
from src.services.workflow_event_service import WorkflowEventService


class ControlDriftService:
    @classmethod
    async def check_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Compare current control states against baseline snapshots to identify regression or coverage drifts."""
        if not prev_snapshot or "summary" not in prev_snapshot:
            return

        from src.services.control_validation_snapshot_service import ControlValidationSnapshotService
        
        curr_snap = await ControlValidationSnapshotService.generate_snapshot(db, scope_id)

        curr_summary = curr_snap["summary"]
        prev_summary = prev_snapshot["summary"]

        # 1. EFFECTIVENESS_CHANGED
        curr_eff = curr_summary.get("average_effectiveness", 100.0)
        prev_eff = prev_summary.get("average_effectiveness", 100.0)
        if curr_eff != prev_eff:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="control_validation.drift",
                payload={
                    "drift_type": "EFFECTIVENESS_CHANGED",
                    "previous_effectiveness": prev_eff,
                    "current_effectiveness": curr_eff,
                },
            )

        # 2. COVERAGE_CHANGED
        curr_cov = curr_snap.get("coverage", {}).get("attack_coverage", 100.0)
        prev_cov = prev_snapshot.get("coverage", {}).get("attack_coverage", 100.0)
        if curr_cov != prev_cov:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="control_validation.drift",
                payload={
                    "drift_type": "COVERAGE_CHANGED",
                    "previous_coverage": prev_cov,
                    "current_coverage": curr_cov,
                },
            )

        # Compare individual controls
        curr_controls = curr_snap.get("controls", {})
        prev_controls = prev_snapshot.get("controls", {})

        for cid_str, prev_ctrl in prev_controls.items():
            curr_ctrl = curr_controls.get(cid_str)
            if not curr_ctrl:
                continue

            # 3. CONTROL_DEGRADED
            if prev_ctrl["status"] == "ACTIVE" and curr_ctrl["status"] == "DEGRADED":
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="control_validation.drift",
                    payload={
                        "drift_type": "CONTROL_DEGRADED",
                        "control_id": cid_str,
                        "name": curr_ctrl["name"],
                    },
                )

            # 4. CONTROL_FAILED
            if prev_ctrl["status"] in ["ACTIVE", "DEGRADED"] and curr_ctrl["status"] == "FAILED":
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="control_validation.drift",
                    payload={
                        "drift_type": "CONTROL_FAILED",
                        "control_id": cid_str,
                        "name": curr_ctrl["name"],
                    },
                )

            # 5. VALIDATION_REGRESSED
            prev_pass = prev_ctrl.get("passed_validations", [])
            curr_fail = curr_ctrl.get("failed_validations", [])
            regressed_techs = set(prev_pass).intersection(set(curr_fail))
            for tech in regressed_techs:
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="control_validation.drift",
                    payload={
                        "drift_type": "VALIDATION_REGRESSED",
                        "control_id": cid_str,
                        "attack_technique": tech,
                    },
                )
