from typing import List, Optional
import uuid
from sqlalchemy.future import select
from src.domain.entities.security_operations_analytics import AnalystPerformanceResponse
from src.infrastructure.database.models import SOCAnalystPerformance
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.core.tenant import get_current_tenant_id


class AnalystPerformanceService:
    @classmethod
    async def clear_analysts(cls) -> None:
        """Clear the analyst store."""
        pass

    @classmethod
    async def seed_analysts_if_empty(cls, uow: Optional[UnitOfWork] = None) -> None:
        """Pre-seed standard analysts to simulate performance rankings."""
        async def _seed(uow_inst: UnitOfWork) -> None:
            existing = await uow_inst.soc_repo.get_analyst_performance()
            if existing:
                return

            tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
            analyst1_id = uuid.UUID("1a1a1a1a-1a1a-1a1a-1a1a-1a1a1a1a1a1a")
            analyst2_id = uuid.UUID("2b2b2b2b-2b2b-2b2b-2b2b-2b2b2b2b2b2b")

            analyst1 = SOCAnalystPerformance(
                analyst_id=analyst1_id,
                analyst_name="Alice Vance",
                alerts_handled=150,
                incidents_handled=12,
                cases_handled=5,
                average_response_time=5.2,
                average_resolution_time=22.4,
                analyst_score=0.0,
                tenant_id=tenant_id
            )

            analyst2 = SOCAnalystPerformance(
                analyst_id=analyst2_id,
                analyst_name="Bob Smith",
                alerts_handled=90,
                incidents_handled=8,
                cases_handled=4,
                average_response_time=12.5,
                average_resolution_time=45.2,
                analyst_score=0.0,
                tenant_id=tenant_id
            )

            await uow_inst.soc_repo.save_analyst_performance(analyst1)
            await uow_inst.soc_repo.save_analyst_performance(analyst2)
            await cls.calculate(uow=uow_inst)

        if uow:
            await _seed(uow)
        else:
            async with UnitOfWork() as uow_new:
                await _seed(uow_new)
                await uow_new.commit()

    @classmethod
    async def calculate(cls, uow: Optional[UnitOfWork] = None) -> None:
        """Calculate and update analyst scores based on handles and response times."""
        async def _calc(uow_inst: UnitOfWork) -> None:
            analysts = await uow_inst.soc_repo.get_analyst_performance()
            for rec in analysts:
                vol_score = float(rec.alerts_handled) * 0.4 + float(rec.incidents_handled) * 2.0 + float(rec.cases_handled) * 5.0
                time_penalty = float(rec.average_response_time) * 0.8 + float(rec.average_resolution_time) * 0.4
                raw_score = max(0.0, 100.0 - time_penalty + vol_score * 0.3)
                rec.analyst_score = round(min(100.0, raw_score), 2)

        if uow:
            await _calc(uow)
        else:
            async with UnitOfWork() as uow_new:
                await _calc(uow_new)
                await uow_new.commit()

    @classmethod
    async def get_analysts(cls) -> List[AnalystPerformanceResponse]:
        """List all analysts."""
        async with UnitOfWork() as uow:
            await cls.seed_analysts_if_empty(uow=uow)
            await uow.commit()
            
        async with UnitOfWork() as uow2:
            analysts = await uow2.soc_repo.get_analyst_performance()
            return [cls.to_response(a) for a in analysts]

    @classmethod
    async def get_rankings(cls) -> List[AnalystPerformanceResponse]:
        """Rank analysts by performance score descending."""
        async with UnitOfWork() as uow:
            await cls.seed_analysts_if_empty(uow=uow)
            await uow.commit()
            
        async with UnitOfWork() as uow2:
            analysts = await uow2.soc_repo.get_analyst_performance()
            sorted_analysts = sorted(analysts, key=lambda x: float(x.analyst_score), reverse=True)
            return [cls.to_response(a) for a in sorted_analysts]

    @classmethod
    def to_response(cls, record: SOCAnalystPerformance) -> AnalystPerformanceResponse:
        return AnalystPerformanceResponse(
            analyst_id=record.analyst_id,
            analyst_name=record.analyst_name,
            alerts_handled=record.alerts_handled,
            incidents_handled=record.incidents_handled,
            cases_handled=record.cases_handled,
            average_response_time=float(record.average_response_time),
            average_resolution_time=float(record.average_resolution_time),
            analyst_score=float(record.analyst_score),
        )
