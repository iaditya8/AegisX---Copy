import uuid
from typing import List, Optional
from sqlalchemy.future import select
from src.infrastructure.repositories.base import BaseRepository
from src.infrastructure.database.models import Remediation, RemediationHistory

class RemediationRepository(BaseRepository[Remediation]):
    def __init__(self, session):
        super().__init__(session, Remediation)

    async def get(self, id: uuid.UUID) -> Optional[Remediation]:
        result = await self.session.execute(
            select(Remediation).filter(Remediation.id == id, Remediation.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list(self) -> List[Remediation]:
        result = await self.session.execute(
            select(Remediation).filter(Remediation.is_deleted == False)
        )
        return list(result.scalars().all())

    async def get_by_fingerprint(self, fingerprint: str) -> Optional[Remediation]:
        result = await self.session.execute(
            select(Remediation).filter(
                Remediation.recommendation_fingerprint == fingerprint,
                Remediation.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def save_history(self, entry: RemediationHistory) -> None:
        self.session.add(entry)

    async def list_history(self, remediation_id: uuid.UUID) -> List[RemediationHistory]:
        result = await self.session.execute(
            select(RemediationHistory).filter(RemediationHistory.remediation_id == remediation_id)
        )
        return list(result.scalars().all())
