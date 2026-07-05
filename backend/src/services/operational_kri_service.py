from typing import List, Optional
import uuid
from datetime import datetime, timezone
from sqlalchemy.future import select
from src.domain.entities.security_operations_analytics import (
    KRIStatus,
    OperationalKRIResponse,
)
from src.services.soc_kri_registry import SOCKRIRegistry
from src.infrastructure.database.models import SOCOperationalKRI
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.core.tenant import get_current_tenant_id


class OperationalKRIService:
    @classmethod
    async def clear_kris(cls) -> None:
        """Clear the KRI store."""
        pass

    @classmethod
    async def seed_kris_if_empty(cls, uow: Optional[UnitOfWork] = None) -> None:
        """Pre-seed standard operational KRIs."""
        async def _seed(uow_inst: UnitOfWork) -> None:
            existing = await uow_inst.soc_repo.get_kris()
            if existing:
                return

            tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
            for kri_name in SOCKRIRegistry.list_types():
                kri = SOCOperationalKRI(
                    kri_id=uuid.uuid4(),
                    kri_name=kri_name,
                    current_value=4.5,
                    threshold_value=5.0,
                    status=KRIStatus.LOW_RISK.value,
                    calculated_at=datetime.now(timezone.utc),
                    tenant_id=tenant_id
                )
                await uow_inst.soc_repo.save_kri(kri)
            await cls.calculate(uow=uow_inst)

        if uow:
            await _seed(uow)
        else:
            async with UnitOfWork() as uow_new:
                await _seed(uow_new)
                await uow_new.commit()

    @classmethod
    async def calculate(cls, uow: Optional[UnitOfWork] = None) -> None:
        """Calculate and refresh KRI risk thresholds status."""
        async def _calc(uow_inst: UnitOfWork) -> None:
            kris = await uow_inst.soc_repo.get_kris()
            for rec in kris:
                curr = float(rec.current_value)
                thresh = float(rec.threshold_value)
                ratio = curr / thresh if thresh > 0 else 1.0
                if ratio >= 1.5:
                    rec.status = KRIStatus.CRITICAL_RISK.value
                elif ratio >= 1.0:
                    rec.status = KRIStatus.HIGH_RISK.value
                elif ratio >= 0.7:
                    rec.status = KRIStatus.MEDIUM_RISK.value
                else:
                    rec.status = KRIStatus.LOW_RISK.value
                rec.calculated_at = datetime.now(timezone.utc)

        if uow:
            await _calc(uow)
        else:
            async with UnitOfWork() as uow_new:
                await _calc(uow_new)
                await uow_new.commit()

    @classmethod
    async def get_kris(cls) -> List[OperationalKRIResponse]:
        """Get all operational KRIs response schemas."""
        async with UnitOfWork() as uow:
            await cls.seed_kris_if_empty(uow=uow)
            await uow.commit()

        async with UnitOfWork() as uow2:
            kris = await uow2.soc_repo.get_kris()
            return [cls.to_response(k) for k in kris]

    @classmethod
    async def set_kri(
        cls, kri_name: str, current_value: float, threshold_value: float, uow: Optional[UnitOfWork] = None
    ) -> SOCOperationalKRI:
        """Manually update or set a KRI."""
        if not SOCKRIRegistry.validate(kri_name):
            raise ValueError(f"Invalid KRI: {kri_name}")

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        async def _set(uow_inst: UnitOfWork) -> SOCOperationalKRI:
            stmt = select(SOCOperationalKRI).filter_by(kri_name=kri_name)
            res = await uow_inst.session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                existing.current_value = current_value
                existing.threshold_value = threshold_value
                await cls.calculate(uow=uow_inst)
                return existing

            record = SOCOperationalKRI(
                kri_id=uuid.uuid4(),
                kri_name=kri_name,
                current_value=current_value,
                threshold_value=threshold_value,
                status=KRIStatus.LOW_RISK.value,
                calculated_at=datetime.now(timezone.utc),
                tenant_id=tenant_id
            )
            await uow_inst.soc_repo.save_kri(record)
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
    def to_response(cls, record: SOCOperationalKRI) -> OperationalKRIResponse:
        return OperationalKRIResponse(
            kri_id=record.kri_id,
            kri_name=record.kri_name,
            current_value=float(record.current_value),
            threshold_value=float(record.threshold_value),
            status=KRIStatus(record.status),
            calculated_at=record.calculated_at,
        )
