from typing import List
import uuid
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import IntelligenceEvent
from src.infrastructure.repositories.base import BaseRepository


class EventRepository(BaseRepository[IntelligenceEvent]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, IntelligenceEvent)

    async def get_pending_events(self, limit: int = 100) -> List[IntelligenceEvent]:
        result = await self.session.execute(
            select(IntelligenceEvent)
            .filter_by(status="pending")
            .order_by(IntelligenceEvent.timestamp.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_as_processed(self, event_id: uuid.UUID) -> None:
        result = await self.session.execute(
            select(IntelligenceEvent).filter_by(id=event_id)
        )
        event = result.scalar_one_or_none()
        if event:
            event.status = "processed"
