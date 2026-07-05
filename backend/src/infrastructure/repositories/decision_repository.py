import uuid
from typing import List, Optional
from sqlalchemy.future import select
from src.infrastructure.repositories.base import BaseRepository
from src.infrastructure.database.models import SecurityDecision, SecurityDecisionHistory

class DecisionRepository(BaseRepository[SecurityDecision]):
    def __init__(self, session):
        super().__init__(session, SecurityDecision)

    async def get(self, id: uuid.UUID) -> Optional[SecurityDecision]:
        result = await self.session.execute(
            select(SecurityDecision).filter(SecurityDecision.id == id, SecurityDecision.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list(self) -> List[SecurityDecision]:
        result = await self.session.execute(
            select(SecurityDecision).filter(SecurityDecision.is_deleted == False)
        )
        return list(result.scalars().all())

    async def get_by_fingerprint(self, fingerprint: str) -> Optional[SecurityDecision]:
        result = await self.session.execute(
            select(SecurityDecision).filter(
                SecurityDecision.decision_fingerprint == fingerprint,
                SecurityDecision.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def save_history(self, entry: SecurityDecisionHistory) -> None:
        self.session.add(entry)

    async def list_history(self, decision_id: uuid.UUID) -> List[SecurityDecisionHistory]:
        result = await self.session.execute(
            select(SecurityDecisionHistory).filter(SecurityDecisionHistory.decision_id == decision_id)
        )
        return list(result.scalars().all())
