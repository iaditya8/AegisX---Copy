import uuid
from typing import List, Optional
from sqlalchemy.future import select
from src.infrastructure.repositories.base import BaseRepository
from src.infrastructure.database.models import Hunt, HuntHypothesis, HuntFinding, HuntHistory

class HuntRepository(BaseRepository[Hunt]):
    def __init__(self, session):
        super().__init__(session, Hunt)

    async def get(self, id: uuid.UUID) -> Optional[Hunt]:
        result = await self.session.execute(
            select(Hunt).filter(Hunt.id == id, Hunt.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list(self) -> List[Hunt]:
        result = await self.session.execute(
            select(Hunt).filter(Hunt.is_deleted == False)
        )
        return list(result.scalars().all())

    async def get_by_fingerprint(self, fingerprint: str) -> Optional[Hunt]:
        result = await self.session.execute(
            select(Hunt).filter(
                Hunt.hunt_fingerprint == fingerprint,
                Hunt.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def save_hypothesis(self, entry: HuntHypothesis) -> None:
        self.session.add(entry)

    async def list_hypotheses(self, hunt_id: uuid.UUID) -> List[HuntHypothesis]:
        result = await self.session.execute(
            select(HuntHypothesis).filter(HuntHypothesis.hunt_id == hunt_id)
        )
        return list(result.scalars().all())

    async def save_finding(self, entry: HuntFinding) -> None:
        self.session.add(entry)

    async def list_findings(self, hunt_id: uuid.UUID) -> List[HuntFinding]:
        result = await self.session.execute(
            select(HuntFinding).filter(HuntFinding.hunt_id == hunt_id)
        )
        return list(result.scalars().all())

    async def save_history(self, entry: HuntHistory) -> None:
        self.session.add(entry)

    async def list_history(self, hunt_id: uuid.UUID) -> List[HuntHistory]:
        result = await self.session.execute(
            select(HuntHistory).filter(HuntHistory.hunt_id == hunt_id)
        )
        return list(result.scalars().all())
