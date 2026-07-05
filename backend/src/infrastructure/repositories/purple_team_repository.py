import uuid
from typing import List, Optional
from sqlalchemy.future import select
from src.infrastructure.repositories.base import BaseRepository
from src.infrastructure.database.models import (
    PurpleTeamExercise,
    PurpleTeamValidation,
    PurpleTeamFinding,
    PurpleTeamHistory
)

class PurpleTeamRepository(BaseRepository[PurpleTeamExercise]):
    def __init__(self, session):
        super().__init__(session, PurpleTeamExercise)

    async def get(self, id: uuid.UUID) -> Optional[PurpleTeamExercise]:
        result = await self.session.execute(
            select(PurpleTeamExercise).filter(PurpleTeamExercise.id == id, PurpleTeamExercise.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list(self) -> List[PurpleTeamExercise]:
        result = await self.session.execute(
            select(PurpleTeamExercise).filter(PurpleTeamExercise.is_deleted == False)
        )
        return list(result.scalars().all())

    async def get_by_fingerprint(self, fingerprint: str) -> Optional[PurpleTeamExercise]:
        result = await self.session.execute(
            select(PurpleTeamExercise).filter(
                PurpleTeamExercise.exercise_fingerprint == fingerprint,
                PurpleTeamExercise.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def save_validation(self, entry: PurpleTeamValidation) -> None:
        self.session.add(entry)

    async def list_validations(self, exercise_id: uuid.UUID) -> List[PurpleTeamValidation]:
        result = await self.session.execute(
            select(PurpleTeamValidation).filter(PurpleTeamValidation.exercise_id == exercise_id)
        )
        return list(result.scalars().all())

    async def save_finding(self, entry: PurpleTeamFinding) -> None:
        self.session.add(entry)

    async def list_findings(self, exercise_id: uuid.UUID) -> List[PurpleTeamFinding]:
        result = await self.session.execute(
            select(PurpleTeamFinding).filter(PurpleTeamFinding.exercise_id == exercise_id)
        )
        return list(result.scalars().all())

    async def save_history(self, entry: PurpleTeamHistory) -> None:
        self.session.add(entry)

    async def list_history(self, exercise_id: uuid.UUID) -> List[PurpleTeamHistory]:
        result = await self.session.execute(
            select(PurpleTeamHistory).filter(PurpleTeamHistory.exercise_id == exercise_id)
        )
        return list(result.scalars().all())
