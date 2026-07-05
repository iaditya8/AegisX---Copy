import uuid
from typing import List, Optional
from sqlalchemy.future import select
from src.infrastructure.repositories.base import BaseRepository
from src.infrastructure.database.models import (
    SecurityProgram,
    SecurityProgramObjective,
    SecurityProgramInitiative,
    SecurityProgramHistory
)

class ProgramRepository(BaseRepository[SecurityProgram]):
    def __init__(self, session):
        super().__init__(session, SecurityProgram)

    async def get(self, id: uuid.UUID) -> Optional[SecurityProgram]:
        result = await self.session.execute(
            select(SecurityProgram).filter(SecurityProgram.id == id, SecurityProgram.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list(self) -> List[SecurityProgram]:
        result = await self.session.execute(
            select(SecurityProgram).filter(SecurityProgram.is_deleted == False)
        )
        return list(result.scalars().all())

    async def get_by_fingerprint(self, fingerprint: str) -> Optional[SecurityProgram]:
        result = await self.session.execute(
            select(SecurityProgram).filter(
                SecurityProgram.program_fingerprint == fingerprint,
                SecurityProgram.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def save_objective(self, entry: SecurityProgramObjective) -> None:
        self.session.add(entry)

    async def list_objectives(self, program_id: uuid.UUID) -> List[SecurityProgramObjective]:
        result = await self.session.execute(
            select(SecurityProgramObjective).filter(SecurityProgramObjective.program_id == program_id)
        )
        return list(result.scalars().all())

    async def save_initiative(self, entry: SecurityProgramInitiative) -> None:
        self.session.add(entry)

    async def list_initiatives(self, program_id: uuid.UUID) -> List[SecurityProgramInitiative]:
        result = await self.session.execute(
            select(SecurityProgramInitiative).filter(SecurityProgramInitiative.program_id == program_id)
        )
        return list(result.scalars().all())

    async def save_history(self, entry: SecurityProgramHistory) -> None:
        self.session.add(entry)

    async def list_history(self, program_id: uuid.UUID) -> List[SecurityProgramHistory]:
        result = await self.session.execute(
            select(SecurityProgramHistory).filter(SecurityProgramHistory.program_id == program_id)
        )
        return list(result.scalars().all())
