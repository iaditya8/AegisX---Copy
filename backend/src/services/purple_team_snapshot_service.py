import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from src.domain.entities.purple_team import ValidationStatus
from src.services.purple_team_service import PurpleTeamService
from src.services.attack_validation_service import AttackValidationService
from src.services.purple_team_coverage_service import PurpleTeamCoverageService


class PurpleTeamSnapshotService:
    # Cache-only store: scope_id (Optional[uuid.UUID]) -> snapshot dict
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear all cached snapshots."""
        cls._snapshots.clear()

    @classmethod
    def generate_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Generate a new snapshot dynamically from active Purple Team records."""
        exercises = PurpleTeamService.get_all_exercises()
        if scope_id:
            exercises = [e for e in exercises if e.scope_id == scope_id]

        exercise_ids = {e.exercise_id for e in exercises}
        validations = [
            v for v in AttackValidationService.get_all_validations()
            if v.exercise_id in exercise_ids
        ]

        total_exercises = len(exercises)
        open_ex = len([e for e in exercises if e.status.value == "OPEN"])
        active_ex = len([e for e in exercises if e.status.value == "ACTIVE"])
        review_ex = len([e for e in exercises if e.status.value == "UNDER_REVIEW"])
        completed_ex = len([e for e in exercises if e.status.value == "COMPLETED"])
        closed_ex = len([e for e in exercises if e.status.value == "CLOSED"])

        passed_val = len([v for v in validations if v.validation_status == ValidationStatus.PASSED])
        partial_val = len([v for v in validations if v.validation_status == ValidationStatus.PARTIAL])
        failed_val = len([v for v in validations if v.validation_status == ValidationStatus.FAILED])

        # Fetch coverage metrics
        coverage_metrics = PurpleTeamCoverageService.calculate_coverage(scope_id)

        snapshot = {
            "summary": {
                "total_exercises": total_exercises,
                "open_exercises": open_ex,
                "active_exercises": active_ex,
                "under_review_exercises": review_ex,
                "completed_exercises": completed_ex,
                "closed_exercises": closed_ex,
                "passed_validations": passed_val,
                "partial_validations": partial_val,
                "failed_validations": failed_val,
            },
            "coverage": coverage_metrics,
            "exercises": {
                str(e.exercise_id): {
                    "name": e.name,
                    "description": e.description,
                    "exercise_type": e.exercise_type.value,
                    "severity": e.severity.value,
                    "status": e.status.value,
                    "owner": e.owner,
                    "scope_id": str(e.scope_id),
                    "related_techniques": e.related_techniques,
                    "related_entities": e.related_entities,
                }
                for e in exercises
            },
            "validations": {
                f"{v.exercise_id}:{v.technique_id}": {
                    "status": v.validation_status.value,
                    "expected": v.expected_detection,
                    "actual": v.actual_detection,
                    "gap": v.coverage_gap,
                }
                for v in validations
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        cls._snapshots[scope_id] = snapshot
        return snapshot

    @classmethod
    def get_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Get the cached snapshot, rebuilding dynamically if missing (consistency)."""
        if scope_id not in cls._snapshots:
            cls.generate_snapshot(scope_id)
        return cls._snapshots[scope_id]
