import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union, Sequence, Any

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.purple_team import (
    ExerciseSeverity,
    ExerciseStatus,
    ExerciseType,
    PurpleTeamExerciseResponse,
)
from src.services.exercise_type_registry import ExerciseTypeRegistry
from src.services.purple_team_fingerprint_service import PurpleTeamFingerprintService
from src.services.purple_team_history_service import PurpleTeamHistoryService
from src.infrastructure.database.models import PurpleTeamExercise as DBExercise, IntelligenceEvent
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.core.tenant import get_current_tenant_id


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
    async def bootstrap(cls, db: AsyncSession) -> None:
        """Bootstrap the L2 cache from PostgreSQL database."""
        cls.clear_exercises()
        async with UnitOfWork() as uow:
            db_exercises = await uow.purple_team_repo.list()
            for db_e in db_exercises:
                # Load related validations to recover techniques
                db_vals = await uow.purple_team_repo.list_validations(db_e.id)
                techniques = [v.technique_id for v in db_vals]

                record = PurpleTeamExerciseRecord(
                    exercise_id=db_e.id,
                    exercise_fingerprint=db_e.exercise_fingerprint,
                    name=db_e.name,
                    description=db_e.description,
                    exercise_type=ExerciseType(db_e.exercise_type),
                    severity=ExerciseSeverity(db_e.severity),
                    status=ExerciseStatus(db_e.status),
                    scope_id=db_e.scope_id,
                    owner=db_e.owner,
                    created_at=db_e.created_at,
                    updated_at=db_e.updated_at,
                    related_techniques=techniques,
                    related_entities=[],
                )
                cls._exercises[db_e.id] = record
                cls._fingerprint_lookup[db_e.exercise_fingerprint] = db_e.id

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
    async def create_or_sync_exercise(
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
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

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
                async with UnitOfWork() as uow:
                    db_e = await uow.purple_team_repo.get(existing.exercise_id)
                    if db_e:
                        db_e.description = existing.description
                        db_e.severity = existing.severity.value
                        db_e.owner = existing.owner
                        db_e.scope_id = existing.scope_id
                        db_e.updated_at = existing.updated_at

                        await PurpleTeamHistoryService.record_event(
                            existing.exercise_id,
                            "UPDATED",
                            f"Exercise updated: severity={existing.severity.value}, status={existing.status.value}",
                            uow=uow,
                        )
                        # Stage outbox event
                        outbox_evt = IntelligenceEvent(
                            tenant_id=tenant_id,
                            event_type="exercise.updated",
                            payload={
                                "exercise_id": str(existing.exercise_id),
                                "status": existing.status.value,
                            }
                        )
                        uow.session.add(outbox_evt)
                        await uow.commit()

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

        async with UnitOfWork() as uow:
            db_e = DBExercise(
                tenant_id=tenant_id,
                id=exercise_id,
                exercise_fingerprint=fingerprint,
                name=name,
                description=description,
                exercise_type=resolved_type.value,
                severity=severity.value,
                status=ExerciseStatus.OPEN.value,
                owner=owner,
                scope_id=scope_id,
            )
            await uow.purple_team_repo.save(db_e)

            await PurpleTeamHistoryService.record_event(
                exercise_id,
                "CREATED",
                f"Created open exercise: '{name}' ({resolved_type.value})",
                uow=uow,
            )

            # Stage outbox event
            outbox_evt = IntelligenceEvent(
                tenant_id=tenant_id,
                event_type="exercise.started",
                payload={
                    "exercise_id": str(exercise_id),
                    "status": ExerciseStatus.OPEN.value,
                }
            )
            uow.session.add(outbox_evt)
            await uow.commit()

        return record

    @classmethod
    async def activate_exercise(cls, exercise_id: uuid.UUID, owner: Optional[str] = None) -> PurpleTeamExerciseRecord:
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

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_e = await uow.purple_team_repo.get(exercise_id)
            if db_e:
                db_e.status = ExerciseStatus.ACTIVE.value
                db_e.updated_at = exercise.updated_at
                if owner:
                    db_e.owner = owner

                await PurpleTeamHistoryService.record_event(
                    exercise_id, "ACTIVATED", f"Exercise activated. Owner: {owner}", uow=uow
                )
                # Stage outbox event
                outbox_evt = IntelligenceEvent(
                    tenant_id=tenant_id,
                    event_type="exercise.status_changed",
                    payload={
                        "exercise_id": str(exercise_id),
                        "status": ExerciseStatus.ACTIVE.value,
                    }
                )
                uow.session.add(outbox_evt)
                await uow.commit()

        return exercise

    @classmethod
    async def review_exercise(cls, exercise_id: uuid.UUID) -> PurpleTeamExerciseRecord:
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

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_e = await uow.purple_team_repo.get(exercise_id)
            if db_e:
                db_e.status = ExerciseStatus.UNDER_REVIEW.value
                db_e.updated_at = exercise.updated_at

                await PurpleTeamHistoryService.record_event(
                    exercise_id, "REVIEWED", "Exercise transitioned to under review", uow=uow
                )
                # Stage outbox event
                outbox_evt = IntelligenceEvent(
                    tenant_id=tenant_id,
                    event_type="exercise.status_changed",
                    payload={
                        "exercise_id": str(exercise_id),
                        "status": ExerciseStatus.UNDER_REVIEW.value,
                    }
                )
                uow.session.add(outbox_evt)
                await uow.commit()

        return exercise

    @classmethod
    async def complete_exercise(cls, exercise_id: uuid.UUID) -> PurpleTeamExerciseRecord:
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

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_e = await uow.purple_team_repo.get(exercise_id)
            if db_e:
                db_e.status = ExerciseStatus.COMPLETED.value
                db_e.updated_at = exercise.updated_at

                await PurpleTeamHistoryService.record_event(
                    exercise_id, "COMPLETED", "Exercise completed", uow=uow
                )
                # Stage outbox event
                outbox_evt = IntelligenceEvent(
                    tenant_id=tenant_id,
                    event_type="exercise.completed",
                    payload={
                        "exercise_id": str(exercise_id),
                        "status": ExerciseStatus.COMPLETED.value,
                    }
                )
                uow.session.add(outbox_evt)
                await uow.commit()

        return exercise

    @classmethod
    async def close_exercise(cls, exercise_id: uuid.UUID) -> PurpleTeamExerciseRecord:
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

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_e = await uow.purple_team_repo.get(exercise_id)
            if db_e:
                db_e.status = ExerciseStatus.CLOSED.value
                db_e.updated_at = exercise.updated_at

                await PurpleTeamHistoryService.record_event(
                    exercise_id, "CLOSED", "Exercise closed (terminal state)", uow=uow
                )
                # Stage outbox event
                outbox_evt = IntelligenceEvent(
                    tenant_id=tenant_id,
                    event_type="exercise.status_changed",
                    payload={
                        "exercise_id": str(exercise_id),
                        "status": ExerciseStatus.CLOSED.value,
                    }
                )
                uow.session.add(outbox_evt)
                await uow.commit()

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
