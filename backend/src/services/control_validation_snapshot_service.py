import uuid
from typing import Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.control_validation import ControlStatus, ValidationStatus
from src.services.control_validation_service import ControlValidationService
from src.services.control_coverage_service import ControlCoverageService


class ControlValidationSnapshotService:
    # Cache store: scope_id -> Snapshot dictionary
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}
    _effectiveness_trends: Dict[Optional[uuid.UUID], List[float]] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear the snapshot cache."""
        cls._snapshots.clear()
        cls._effectiveness_trends.clear()

    @classmethod
    def get_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Retrieve the cached snapshot, defaulting to a minimal fallback if missing or corrupted."""
        snap = cls._snapshots.get(scope_id)
        if not snap or not isinstance(snap, dict) or "summary" not in snap:
            return {
                "summary": {
                    "total_controls": 0,
                    "active_count": 0,
                    "degraded_count": 0,
                    "failed_count": 0,
                    "average_effectiveness": 100.0,
                    "validation_success_rate": 100.0,
                    "trends": cls._effectiveness_trends.setdefault(scope_id, [100.0]),
                },
                "coverage": {
                    "attack_coverage": 100.0,
                    "detection_coverage": 100.0,
                    "purple_team_coverage": 100.0,
                    "hunt_coverage": 100.0,
                    "exposure_coverage": 100.0,
                },
                "controls": {},
            }
        return snap

    @classmethod
    async def generate_snapshot(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None
    ) -> dict:
        """Dynamically rebuild snapshot stats from active control records."""
        all_controls = ControlValidationService.get_all_controls()
        if scope_id:
            all_controls = [c for c in all_controls if c.scope_id == scope_id]

        total_controls = len(all_controls)
        active_ctrls = [c for c in all_controls if c.status != ControlStatus.RETIRED]

        # Calculate status counts
        active_count = sum(1 for c in all_controls if c.status == ControlStatus.ACTIVE)
        degraded_count = sum(1 for c in all_controls if c.status == ControlStatus.DEGRADED)
        failed_count = sum(1 for c in all_controls if c.status == ControlStatus.FAILED)

        # Average effectiveness
        if active_ctrls:
            avg_eff = round(sum(c.effectiveness_score for c in active_ctrls) / len(active_ctrls), 2)
        else:
            avg_eff = 100.0

        # Success rate and lists of pass/fail techs
        total_vals = 0
        passed_vals = 0
        controls_track = {}

        for c in all_controls:
            vals = ControlValidationService.get_validations(c.control_id)
            total_vals += len(vals)
            
            passed_techs = []
            failed_techs = []
            for v in vals:
                status_str = str(v.validation_status.value).upper()
                if "PASS" in status_str:
                    passed_vals += 1
                    passed_techs.append(v.attack_technique)
                else:
                    failed_techs.append(v.attack_technique)

            controls_track[str(c.control_id)] = {
                "control_id": str(c.control_id),
                "control_fingerprint": c.control_fingerprint,
                "name": c.name,
                "status": c.status.value,
                "effectiveness_score": c.effectiveness_score,
                "passed_validations": passed_techs,
                "failed_validations": failed_techs,
            }

        success_rate = round((passed_vals / total_vals) * 100.0, 2) if total_vals else 100.0

        # Calculate coverage details
        cov_details = await ControlCoverageService.calculate_coverage(db, scope_id)

        # Update trend history
        trends = cls._effectiveness_trends.setdefault(scope_id, [])
        trends.append(avg_eff)
        if len(trends) > 10:
            trends.pop(0)

        snapshot = {
            "summary": {
                "total_controls": total_controls,
                "active_count": active_count,
                "degraded_count": degraded_count,
                "failed_count": failed_count,
                "average_effectiveness": avg_eff,
                "validation_success_rate": success_rate,
                "trends": list(trends),
            },
            "coverage": cov_details,
            "controls": controls_track,
        }

        cls._snapshots[scope_id] = snapshot
        return snapshot
