from typing import List, Optional
import uuid
from sqlalchemy.future import select
from src.infrastructure.database.models import (
    CyberRiskRecord,
    CyberRiskScenario,
    CyberRiskForecast,
    CyberRiskHistory,
)
from src.infrastructure.repositories.base import BaseRepository


class CyberRiskRepository(BaseRepository[CyberRiskRecord]):
    def __init__(self, session):
        super().__init__(session, CyberRiskRecord)

    async def get_risk_by_fingerprint(self, tenant_id: uuid.UUID, fingerprint: str) -> Optional[CyberRiskRecord]:
        result = await self.session.execute(
            select(CyberRiskRecord).filter(
                CyberRiskRecord.tenant_id == tenant_id,
                CyberRiskRecord.risk_fingerprint == fingerprint,
                CyberRiskRecord.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def get_active_risks(self, tenant_id: uuid.UUID) -> List[CyberRiskRecord]:
        result = await self.session.execute(
            select(CyberRiskRecord).filter(
                CyberRiskRecord.tenant_id == tenant_id,
                CyberRiskRecord.status == "ACTIVE",
                CyberRiskRecord.is_deleted == False
            )
        )
        return list(result.scalars().all())

    async def get_scenarios(self) -> List[CyberRiskScenario]:
        result = await self.session.execute(
            select(CyberRiskScenario).filter(CyberRiskScenario.is_deleted == False)
        )
        return list(result.scalars().all())

    async def save_scenario(self, scenario: CyberRiskScenario) -> None:
        self.session.add(scenario)

    async def get_forecasts(self, risk_id: uuid.UUID) -> List[CyberRiskForecast]:
        result = await self.session.execute(
            select(CyberRiskForecast).filter(
                CyberRiskForecast.risk_id == risk_id,
                CyberRiskForecast.is_deleted == False
            )
        )
        return list(result.scalars().all())

    async def save_forecast(self, forecast: CyberRiskForecast) -> None:
        self.session.add(forecast)

    async def get_history(self, risk_id: uuid.UUID) -> List[CyberRiskHistory]:
        result = await self.session.execute(
            select(CyberRiskHistory)
            .filter(
                CyberRiskHistory.risk_id == risk_id,
                CyberRiskHistory.is_deleted == False
            )
            .order_by(CyberRiskHistory.timestamp.desc())
        )
        return list(result.scalars().all())

    async def save_history(self, history_entry: CyberRiskHistory) -> None:
        self.session.add(history_entry)
