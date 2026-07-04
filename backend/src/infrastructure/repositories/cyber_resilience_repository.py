from typing import List, Optional
import uuid
from sqlalchemy.future import select
from src.infrastructure.database.models import CyberResilienceRecord, RecoveryObjective, CyberResilienceHistory
from src.infrastructure.repositories.base import BaseRepository


class CyberResilienceRepository(BaseRepository[CyberResilienceRecord]):
    def __init__(self, session):
        super().__init__(session, CyberResilienceRecord)

    async def get_objectives(self, resilience_id: uuid.UUID) -> List[RecoveryObjective]:
        result = await self.session.execute(
            select(RecoveryObjective).filter_by(resilience_id=resilience_id)
        )
        return list(result.scalars().all())

    async def save_objective(self, objective: RecoveryObjective) -> None:
        self.session.add(objective)

    async def get_history(self, resilience_id: uuid.UUID) -> List[CyberResilienceHistory]:
        result = await self.session.execute(
            select(CyberResilienceHistory)
            .filter_by(resilience_id=resilience_id)
            .order_by(CyberResilienceHistory.timestamp.desc())
        )
        return list(result.scalars().all())

    async def save_history(self, history_entry: CyberResilienceHistory) -> None:
        self.session.add(history_entry)
