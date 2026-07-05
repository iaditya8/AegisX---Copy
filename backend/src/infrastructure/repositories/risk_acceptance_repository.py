import uuid
from typing import List, Optional
from sqlalchemy.future import select
from src.infrastructure.repositories.base import BaseRepository
from src.infrastructure.database.models import RiskAcceptance

class RiskAcceptanceRepository(BaseRepository[RiskAcceptance]):
    def __init__(self, session):
        super().__init__(session, RiskAcceptance)

    async def get(self, id: uuid.UUID) -> Optional[RiskAcceptance]:
        result = await self.session.execute(
            select(RiskAcceptance).filter(RiskAcceptance.id == id, RiskAcceptance.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list(self) -> List[RiskAcceptance]:
        result = await self.session.execute(
            select(RiskAcceptance).filter(RiskAcceptance.is_deleted == False)
        )
        return list(result.scalars().all())

    async def get_by_fingerprint(self, fingerprint: str) -> Optional[RiskAcceptance]:
        result = await self.session.execute(
            select(RiskAcceptance).filter(
                RiskAcceptance.recommendation_fingerprint == fingerprint,
                RiskAcceptance.is_deleted == False
            )
        )
        return result.scalar_one_or_none()
