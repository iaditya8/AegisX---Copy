import uuid
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.purple_team import ExerciseType, ValidationStatus
from src.services.purple_team_service import PurpleTeamService
from src.services.attack_validation_service import AttackValidationService
from src.services.purple_team_coverage_service import PurpleTeamCoverageService
from src.services.workflow_event_service import WorkflowEventService


class PurpleTeamDriftService:
    @classmethod
    async def check_drift(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None, prev_snapshot: Optional[dict] = None
    ) -> None:
        """Evaluate Purple Team regressions, gaps, and coverage drifts to emit workflow events."""
        if not prev_snapshot:
            return

        # 1. Fetch current exercises and validations
        exercises = PurpleTeamService.get_all_exercises()
        validations = AttackValidationService.get_all_validations()

        if scope_id:
            exercises = [e for e in exercises if e.scope_id == scope_id]
            exercise_ids = {e.exercise_id for e in exercises}
            validations = [v for v in validations if v.exercise_id in exercise_ids]

        current_val_lookup = {f"{v.exercise_id}:{v.technique_id}": v for v in validations}
        prev_vals = prev_snapshot.get("validations", {})

        status_hierarchy = {
            ValidationStatus.PASSED: 3,
            ValidationStatus.PARTIAL: 2,
            ValidationStatus.FAILED: 1,
        }

        # Check validation regressions
        for key, curr_v in current_val_lookup.items():
            prev_v = prev_vals.get(key)
            if prev_v:
                prev_status_str = prev_v.get("status")
                if not prev_status_str:
                    continue

                prev_status_val = status_hierarchy.get(ValidationStatus(prev_status_str), 1)
                curr_status_val = status_hierarchy.get(curr_v.validation_status, 1)

                if curr_status_val < prev_status_val:
                    exercise = PurpleTeamService.get_exercise(curr_v.exercise_id)
                    drift_type = "VALIDATION_REGRESSION"
                    if exercise:
                        if exercise.exercise_type == ExerciseType.DETECTION_VALIDATION:
                            drift_type = "DETECTION_DRIFT"
                        elif exercise.exercise_type == ExerciseType.CONTROL_VALIDATION:
                            drift_type = "CONTROL_DRIFT"

                    await WorkflowEventService.emit_event(
                        db=db,
                        event_type="purple_team.drift",
                        correlation_id=curr_v.exercise_id,
                        payload={
                            "drift_type": drift_type,
                            "exercise_id": str(curr_v.exercise_id),
                            "technique_id": curr_v.technique_id,
                            "previous_status": prev_status_str,
                            "current_status": curr_v.validation_status.value,
                        },
                    )

        # 2. Check coverage regression
        prev_cov = prev_snapshot.get("coverage", {})
        curr_cov = PurpleTeamCoverageService.calculate_coverage(scope_id)

        if prev_cov:
            coverage_decreased = False
            for k, val in curr_cov.items():
                if val < prev_cov.get(k, 100.0):
                    coverage_decreased = True
                    break

            if coverage_decreased:
                drift_type = "COVERAGE_REGRESSION"
                if curr_cov["attack_coverage"] < prev_cov.get("attack_coverage", 100.0):
                    drift_type = "NEW_ATTACK_GAP"

                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="purple_team.coverage_changed",
                    payload={
                        "drift_type": drift_type,
                        "previous_coverage": prev_cov,
                        "current_coverage": curr_cov,
                    },
                )
