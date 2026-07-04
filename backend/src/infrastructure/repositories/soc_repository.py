from typing import List, Optional
import uuid
from sqlalchemy.future import select
from src.infrastructure.database.models import (
    SOCAnalyticsRecord,
    SOCAnalystPerformance,
    SOCOperationalKPI,
    SOCOperationalKRI,
    SOCAnalyticsHistory,
)
from src.infrastructure.repositories.base import BaseRepository


class SOCRepository(BaseRepository[SOCAnalyticsRecord]):
    def __init__(self, session):
        super().__init__(session, SOCAnalyticsRecord)

    async def get_analyst_performance(self) -> List[SOCAnalystPerformance]:
        result = await self.session.execute(select(SOCAnalystPerformance))
        return list(result.scalars().all())

    async def save_analyst_performance(self, performance: SOCAnalystPerformance) -> None:
        self.session.add(performance)

    async def get_kpis(self) -> List[SOCOperationalKPI]:
        result = await self.session.execute(select(SOCOperationalKPI))
        return list(result.scalars().all())

    async def save_kpi(self, kpi: SOCOperationalKPI) -> None:
        self.session.add(kpi)

    async def get_kris(self) -> List[SOCOperationalKRI]:
        result = await self.session.execute(select(SOCOperationalKRI))
        return list(result.scalars().all())

    async def save_kri(self, kri: SOCOperationalKRI) -> None:
        self.session.add(kri)

    async def get_history(self, analytics_id: uuid.UUID) -> List[SOCAnalyticsHistory]:
        result = await self.session.execute(
            select(SOCAnalyticsHistory)
            .filter_by(analytics_id=analytics_id)
            .order_by(SOCAnalyticsHistory.timestamp.desc())
        )
        return list(result.scalars().all())

    async def save_history(self, history_entry: SOCAnalyticsHistory) -> None:
        self.session.add(history_entry)
