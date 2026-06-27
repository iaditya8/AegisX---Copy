import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.purple_team import ValidationStatus
from src.domain.entities.detection import DetectionStatus
from src.infrastructure.database.models import Asset, Finding
from src.services.purple_team_service import PurpleTeamService
from src.services.detection_service import DetectionService
from src.services.hunt_service import HuntService
from src.services.purple_team_history_service import PurpleTeamHistoryService


class ValidationRecord:
    def __init__(
        self,
        validation_id: uuid.UUID,
        exercise_id: uuid.UUID,
        technique_id: str,
        validation_status: ValidationStatus,
        expected_detection: bool,
        actual_detection: bool,
        coverage_gap: bool,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.validation_id = validation_id
        self.exercise_id = exercise_id
        self.technique_id = technique_id
        self.validation_status = validation_status
        self.expected_detection = expected_detection
        self.actual_detection = actual_detection
        self.coverage_gap = coverage_gap
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)


class AttackValidationService:
    # in-memory store: validation_id -> ValidationRecord
    _validations: Dict[uuid.UUID, ValidationRecord] = {}

    @classmethod
    def clear_validations(cls) -> None:
        """Clear all validation records."""
        cls._validations.clear()

    @classmethod
    def get_all_validations(cls) -> List[ValidationRecord]:
        """Retrieve all validation records."""
        return list(cls._validations.values())

    @classmethod
    def get_validation(cls, validation_id: uuid.UUID) -> Optional[ValidationRecord]:
        """Retrieve a validation record by ID."""
        return cls._validations.get(validation_id)

    @classmethod
    def get_exercise_validations(cls, exercise_id: uuid.UUID) -> List[ValidationRecord]:
        """Retrieve all validation records for an exercise."""
        return [v for v in cls._validations.values() if v.exercise_id == exercise_id]

    @classmethod
    async def validate_exercise_techniques(cls, db: AsyncSession, exercise_id: uuid.UUID) -> List[ValidationRecord] :
        """Perform ATT&CK technique validation against active platform state, preserving identity rules."""
        exercise = PurpleTeamService.get_exercise(exercise_id)
        if not exercise:
            raise ValueError(f"Exercise {exercise_id} not found")

        # 1. Fetch active findings inside this scope to check actual detections
        q_findings = (
            select(Finding)
            .join(Asset)
            .where(Asset.scope_id == exercise.scope_id, Asset.deleted_at.is_(None))
        )
        res_findings = await db.execute(q_findings)
        findings = list(res_findings.scalars().all())

        # Fetch active detections in the system
        detections = DetectionService.get_all_detections()
        # Filter detections active for this scope or globally
        active_detections = [
            d for d in detections
            if d.status == DetectionStatus.ACTIVE and (not d.scope_id or d.scope_id == exercise.scope_id)
        ]

        # Fetch hunts in this scope
        hunts = HuntService.get_all_hunts()
        scope_hunts = [h for h in hunts if h.scope_id == exercise.scope_id]

        outcomes = []
        for tech in exercise.related_techniques:
            # check expected detection (active rule covers the technique)
            expected = any(tech in d.attack_techniques for d in active_detections)

            # check actual detection
            actual = False
            # Check findings referencing this technique in title/desc
            for f in findings:
                if tech in str(f.title) or tech in str(f.description):
                    actual = True
                    break
            # Check hunts referencing this technique in title/desc
            if not actual:
                for h in scope_hunts:
                    if tech in str(h.title) or tech in str(h.description):
                        actual = True
                        break

            # determine status and gap
            gap = not expected
            if expected and actual:
                status = ValidationStatus.PASSED
            elif expected and not actual:
                status = ValidationStatus.PARTIAL
            else:
                status = ValidationStatus.FAILED

            # Validation Identity Preservation Rule:
            # Look for existing validation with same (exercise_id, technique_id)
            existing_match = None
            for v in cls._validations.values():
                if v.exercise_id == exercise_id and v.technique_id == tech:
                    existing_match = v
                    break

            if existing_match:
                # Sync status, expected, actual, gap and timestamps
                changed = False
                if existing_match.validation_status != status:
                    existing_match.validation_status = status
                    changed = True
                if existing_match.expected_detection != expected:
                    existing_match.expected_detection = expected
                    changed = True
                if existing_match.actual_detection != actual:
                    existing_match.actual_detection = actual
                    changed = True
                if existing_match.coverage_gap != gap:
                    existing_match.coverage_gap = gap
                    changed = True

                if changed:
                    existing_match.updated_at = datetime.now(timezone.utc)
                    PurpleTeamHistoryService.record_event(
                        exercise_id,
                        "VALIDATED",
                        f"Validation status updated for technique {tech}: {status.value}",
                    )
                outcomes.append(existing_match)
            else:
                # Create a new validation record
                val_id = uuid.uuid4()
                record = ValidationRecord(
                    validation_id=val_id,
                    exercise_id=exercise_id,
                    technique_id=tech,
                    validation_status=status,
                    expected_detection=expected,
                    actual_detection=actual,
                    coverage_gap=gap,
                )
                cls._validations[val_id] = record
                PurpleTeamHistoryService.record_event(
                    exercise_id,
                    "VALIDATED",
                    f"Validation completed for technique {tech}: {status.value}",
                )
                outcomes.append(record)

        return outcomes
