import uuid
from typing import List, Optional
from sqlalchemy.future import select
from src.infrastructure.repositories.base import BaseRepository
from src.infrastructure.database.models import SecurityPosture, SecurityPostureHistory

class PostureRepository(BaseRepository[SecurityPosture]):
    def __init__(self, session):
        super().__init__(session, SecurityPosture)

    async def get(self, id: uuid.UUID) -> Optional[SecurityPosture]:
        result = await self.session.execute(
            select(SecurityPosture).filter(SecurityPosture.id == id, SecurityPosture.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list(self) -> List[SecurityPosture]:
        result = await self.session.execute(
            select(SecurityPosture).filter(SecurityPosture.is_deleted == False)
        )
        return list(result.scalars().all())

    async def get_by_fingerprint(self, fingerprint: str) -> Optional[SecurityPosture]:
        result = await self.session.execute(
            select(SecurityPosture).filter(
                SecurityPosture.posture_fingerprint == fingerprint,
                SecurityPosture.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def save_history(self, entry: SecurityPostureHistory) -> None:
        self.session.add(entry)

    async def list_history(self, posture_id: uuid.UUID) -> List[SecurityPostureHistory]:
        result = await self.session.execute(
            select(SecurityPostureHistory).filter(SecurityPostureHistory.posture_id == posture_id)
        )
        return list(result.scalars().all())
