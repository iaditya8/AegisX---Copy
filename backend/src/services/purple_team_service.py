import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union, Sequence

from src.domain.entities.purple_team import (
    ExerciseSeverity,
    ExerciseStatus,
    ExerciseType,
    PurpleTeamExerciseResponse,
)
from src.services.exercise_type_registry import ExerciseTypeRegistry
from src.services.purple_team_fingerprint_service import PurpleTeamFingerprintService
from src.services.purple_team_history_service import PurpleTeamHistoryService


class PurpleTeamExerciseRecord:
    def __init__(
        self,
        exercise_id: uuid.UUID,
        exercise_fingerprint: str,
        name: str,
        description: str,
        exercise_type: ExerciseType,
        severity: ExerciseSeverity,
        status: ExerciseStatus,
        scope_id: uuid.UUID,
        owner: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        related_techniques: Optional[List[str]] = None,
        related_entities: Optional[List[dict]] = None,
    ):
        self.exercise_id = exercise_id
        self.exercise_fingerprint = exercise_fingerprint
        self.name = name
        self.description = description
        self.exercise_type = exercise_type
        self.severity = severity
        self.status = status
        self.scope_id = scope_id
        self.owner = owner
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
        self.related_techniques = related_techniques or []
        self.related_entities = related_entities or []


class PurpleTeamService:
    # in-memory store: exercise_id -> PurpleTeamExerciseRecord
    _exercises: Dict[uuid.UUID, PurpleTeamExerciseRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def clear_exercises(cls) -> None:
        """Clear all exercise records."""
        cls._exercises.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_exercises(cls) -> List[PurpleTeamExerciseRecord]:
        """Retrieve all exercises."""
        return list(cls._exercises.values())

    @classmethod
    def get_exercise(cls, exercise_id: uuid.UUID) -> Optional[PurpleTeamExerciseRecord]:
        """Retrieve an exercise by ID."""
        return cls._exercises.get(exercise_id)

    @classmethod
    def get_exercise_by_fingerprint(cls, fingerprint: str) -> Optional[PurpleTeamExerciseRecord]:
        """Retrieve an exercise by fingerprint."""
        exercise_id = cls._fingerprint_lookup.get(fingerprint)
        if exercise_id:
            return cls.get_exercise(exercise_id)
        return None

    @classmethod
    def create_or_sync_exercise(
        cls,
        name: str,
        description: str,
        exercise_type: ExerciseType,
        severity: ExerciseSeverity,
        scope_id: uuid.UUID,
        owner: Optional[str] = None,
        related_techniques: Optional[Sequence[str]] = None,
        related_entities: Optional[Sequence[Union[dict, str]]] = None,
    ) -> PurpleTeamExerciseRecord:
        """Create a new exercise or sync with an existing one based on fingerprint stability rules."""
        if not ExerciseTypeRegistry.is_valid_type(exercise_type):
            raise ValueError(f"Invalid exercise type: {exercise_type}")

        resolved_type = ExerciseTypeRegistry.resolve_type(exercise_type)
        techniques = list(related_techniques) if related_techniques is not None else []
        entities = list(related_entities) if related_entities is not None else []

        # Convert entities to standard dict list format if needed
        standard_entities = []
        for entity in entities:
            if isinstance(entity, dict):
                standard_entities.append(entity)
            else:
                standard_entities.append({"entity_type": "Asset", "entity_id": str(entity)})

        fingerprint = PurpleTeamFingerprintService.generate_fingerprint(
            resolved_type, name, techniques, entities
        )

        existing = cls.get_exercise_by_fingerprint(fingerprint)
        if existing:
            if existing.status == ExerciseStatus.CLOSED:
                # CLOSED is a terminal state. Sync should not modify closed exercises.
                return existing

            # Sync rules: preserve identity, status, history, findings linkage, and timestamps
            changed = False
            if existing.description != description:
                existing.description = description
                changed = True
            if existing.severity != severity:
                existing.severity = severity
                changed = True
            if owner and existing.owner != owner:
                existing.owner = owner
                changed = True
            if existing.scope_id != scope_id:
                existing.scope_id = scope_id
                changed = True

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
                PurpleTeamHistoryService.record_event(
                    existing.exercise_id,
                    "UPDATED",
                    f"Exercise updated: severity={existing.severity.value}, status={existing.status.value}",
                )
            return existing

        # Create new open exercise
        exercise_id = uuid.uuid4()
        record = PurpleTeamExerciseRecord(
            exercise_id=exercise_id,
            exercise_fingerprint=fingerprint,
            name=name,
            description=description,
            exercise_type=resolved_type,
            severity=severity,
            status=ExerciseStatus.OPEN,
            scope_id=scope_id,
            owner=owner,
            related_techniques=techniques,
            related_entities=standard_entities,
        )
        cls._exercises[exercise_id] = record
        cls._fingerprint_lookup[fingerprint] = exercise_id

        PurpleTeamHistoryService.record_event(
            exercise_id,
            "CREATED",
            f"Created open exercise: '{name}' ({resolved_type.value})",
        )
        return record

    @classmethod
    def activate_exercise(cls, exercise_id: uuid.UUID, owner: Optional[str] = None) -> PurpleTeamExerciseRecord:
        """Transition exercise to ACTIVE status (from OPEN or UNDER_REVIEW)."""
        exercise = cls.get_exercise(exercise_id)
        if not exercise:
            raise ValueError(f"Exercise {exercise_id} not found")

        if exercise.status == ExerciseStatus.CLOSED:
            raise ValueError("CLOSED is a terminal state and cannot transition back to active")

        if exercise.status == ExerciseStatus.ACTIVE:
            return exercise

        if exercise.status not in [ExerciseStatus.OPEN, ExerciseStatus.UNDER_REVIEW]:
            raise ValueError(f"Cannot transition to ACTIVE from status {exercise.status.value}")

        exercise.status = ExerciseStatus.ACTIVE
        exercise.updated_at = datetime.now(timezone.utc)
        if owner:
            exercise.owner = owner

        PurpleTeamHistoryService.record_event(
            exercise_id, "ACTIVATED", f"Exercise activated. Owner: {owner}"
        )
        return exercise

    @classmethod
    def review_exercise(cls, exercise_id: uuid.UUID) -> PurpleTeamExerciseRecord:
        """Transition exercise to UNDER_REVIEW status (from ACTIVE)."""
        exercise = cls.get_exercise(exercise_id)
        if not exercise:
            raise ValueError(f"Exercise {exercise_id} not found")

        if exercise.status == ExerciseStatus.CLOSED:
            raise ValueError("CLOSED is a terminal state")

        if exercise.status == ExerciseStatus.UNDER_REVIEW:
            return exercise

        if exercise.status != ExerciseStatus.ACTIVE:
            raise ValueError(f"Cannot transition to UNDER_REVIEW from status {exercise.status.value}")

        exercise.status = ExerciseStatus.UNDER_REVIEW
        exercise.updated_at = datetime.now(timezone.utc)

        PurpleTeamHistoryService.record_event(
            exercise_id, "REVIEWED", "Exercise transitioned to under review"
        )
        return exercise

    @classmethod
    def complete_exercise(cls, exercise_id: uuid.UUID) -> PurpleTeamExerciseRecord:
        """Transition exercise to COMPLETED status (from ACTIVE or UNDER_REVIEW)."""
        exercise = cls.get_exercise(exercise_id)
        if not exercise:
            raise ValueError(f"Exercise {exercise_id} not found")

        if exercise.status == ExerciseStatus.CLOSED:
            raise ValueError("CLOSED is a terminal state")

        if exercise.status == ExerciseStatus.COMPLETED:
            return exercise

        if exercise.status not in [ExerciseStatus.ACTIVE, ExerciseStatus.UNDER_REVIEW]:
            raise ValueError(f"Cannot transition to COMPLETED from status {exercise.status.value}")

        exercise.status = ExerciseStatus.COMPLETED
        exercise.updated_at = datetime.now(timezone.utc)

        PurpleTeamHistoryService.record_event(
            exercise_id, "COMPLETED", "Exercise completed"
        )
        return exercise

    @classmethod
    def close_exercise(cls, exercise_id: uuid.UUID) -> PurpleTeamExerciseRecord:
        """Transition exercise to CLOSED status (terminal state, from COMPLETED)."""
        exercise = cls.get_exercise(exercise_id)
        if not exercise:
            raise ValueError(f"Exercise {exercise_id} not found")

        if exercise.status == ExerciseStatus.CLOSED:
            return exercise

        if exercise.status != ExerciseStatus.COMPLETED:
            raise ValueError(f"Cannot transition to CLOSED from status {exercise.status.value}")

        exercise.status = ExerciseStatus.CLOSED
        exercise.updated_at = datetime.now(timezone.utc)

        PurpleTeamHistoryService.record_event(
            exercise_id, "CLOSED", "Exercise closed (terminal state)"
        )
        return exercise

    @classmethod
    def to_response(cls, record: PurpleTeamExerciseRecord) -> PurpleTeamExerciseResponse:
        """Convert a PurpleTeamExerciseRecord into a PurpleTeamExerciseResponse."""
        return PurpleTeamExerciseResponse(
            exercise_id=record.exercise_id,
            exercise_fingerprint=record.exercise_fingerprint,
            name=record.name,
            description=record.description,
            exercise_type=record.exercise_type,
            severity=record.severity,
            status=record.status,
            owner=record.owner,
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
