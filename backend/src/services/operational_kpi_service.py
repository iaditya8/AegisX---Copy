from typing import List, Optional
import uuid
from datetime import datetime, timezone
from sqlalchemy.future import select
from src.domain.entities.security_operations_analytics import (
    KPIStatus,
    OperationalKPIResponse,
)
from src.services.soc_kpi_registry import SOCKPIRegistry
from src.infrastructure.database.models import SOCOperationalKPI
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.core.tenant import get_current_tenant_id


class OperationalKPIService:
    @classmethod
    async def clear_kpis(cls) -> None:
        """Clear the KPI store."""
        pass

    @classmethod
    async def seed_kpis_if_empty(cls, uow: Optional[UnitOfWork] = None) -> None:
        """Pre-seed standard operational KPIs."""
        async def _seed(uow_inst: UnitOfWork) -> None:
            existing = await uow_inst.soc_repo.get_kpis()
            if existing:
                return

            tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
            for kpi_name in SOCKPIRegistry.list_types():
                kpi = SOCOperationalKPI(
                    kpi_id=uuid.uuid4(),
                    kpi_name=kpi_name,
                    current_value=15.0 if "Mean Time" in kpi_name else 85.0,
                    target_value=10.0 if "Mean Time" in kpi_name else 90.0,
                    status=KPIStatus.AT_RISK.value,
                    calculated_at=datetime.now(timezone.utc),
                    tenant_id=tenant_id
                )
                await uow_inst.soc_repo.save_kpi(kpi)
            await cls.calculate(uow=uow_inst)

        if uow:
            await _seed(uow)
        else:
            async with UnitOfWork() as uow_new:
                await _seed(uow_new)
                await uow_new.commit()

    @classmethod
    async def calculate(cls, uow: Optional[UnitOfWork] = None) -> None:
        """Calculate and refresh KPI targets compliance status."""
        async def _calc(uow_inst: UnitOfWork) -> None:
            kpis = await uow_inst.soc_repo.get_kpis()
            for rec in kpis:
                curr = float(rec.current_value)
                targ = float(rec.target_value)
                if "Mean Time" in rec.kpi_name:
                    if curr <= targ:
                        rec.status = KPIStatus.ON_TARGET.value
                    elif curr <= targ * 1.5:
                        rec.status = KPIStatus.AT_RISK.value
                    else:
                        rec.status = KPIStatus.OFF_TARGET.value
                else:
                    if curr >= targ:
                        rec.status = KPIStatus.ON_TARGET.value
                    elif curr >= targ * 0.85:
                        rec.status = KPIStatus.AT_RISK.value
                    else:
                        rec.status = KPIStatus.OFF_TARGET.value
                rec.calculated_at = datetime.now(timezone.utc)

        if uow:
            await _calc(uow)
        else:
            async with UnitOfWork() as uow_new:
                await _calc(uow_new)
                await uow_new.commit()

    @classmethod
    async def get_kpis(cls) -> List[OperationalKPIResponse]:
        """Get all operational KPIs response schemas."""
        async with UnitOfWork() as uow:
            await cls.seed_kpis_if_empty(uow=uow)
            await uow.commit()

        async with UnitOfWork() as uow2:
            kpis = await uow2.soc_repo.get_kpis()
            return [cls.to_response(k) for k in kpis]

    @classmethod
    async def set_kpi(
        cls, kpi_name: str, current_value: float, target_value: float, uow: Optional[UnitOfWork] = None
    ) -> SOCOperationalKPI:
        """Manually update or set a KPI."""
        if not SOCKPIRegistry.validate(kpi_name):
            raise ValueError(f"Invalid KPI: {kpi_name}")

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        async def _set(uow_inst: UnitOfWork) -> SOCOperationalKPI:
            stmt = select(SOCOperationalKPI).filter_by(kpi_name=kpi_name)
            res = await uow_inst.session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                existing.current_value = current_value
                existing.target_value = target_value
                await cls.calculate(uow=uow_inst)
                return existing

            record = SOCOperationalKPI(
                kpi_id=uuid.uuid4(),
                kpi_name=kpi_name,
                current_value=current_value,
                target_value=target_value,
                status=KPIStatus.AT_RISK.value,
                calculated_at=datetime.now(timezone.utc),
                tenant_id=tenant_id
            )
            await uow_inst.soc_repo.save_kpi(record)
            await cls.calculate(uow=uow_inst)
            return record

        if uow:
            return await _set(uow)
        else:
            async with UnitOfWork() as uow_new:
                rec = await _set(uow_new)
                await uow_new.commit()
                return rec

    @classmethod
    def to_response(cls, record: SOCOperationalKPI) -> OperationalKPIResponse:
        return OperationalKPIResponse(
            kpi_id=record.kpi_id,
            kpi_name=record.kpi_name,
            current_value=float(record.current_value),
            target_value=float(record.target_value),
            status=KPIStatus(record.status),
            calculated_at=record.calculated_at,
        )
