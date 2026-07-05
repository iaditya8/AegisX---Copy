import uuid
from datetime import datetime, timezone
from typing import List, Optional
from src.domain.entities.cyber_risk_quantification import RiskHistoryEntry
from src.infrastructure.database.models import CyberRiskHistory
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.core.tenant import get_current_tenant_id


class QuantifiedRiskHistoryService:
    @classmethod
    async def clear_history(cls) -> None:
        """Clear all logged operational risk history."""
        pass

    @classmethod
    async def get_history(cls, risk_id: uuid.UUID) -> List[RiskHistoryEntry]:
        """Get all logged history for a risk record."""
        async with UnitOfWork() as uow:
            records = await uow.risk_repo.get_history(risk_id)
            return [cls.to_response(r) for r in records]

    @classmethod
    async def record_event(
        cls,
        risk_id: uuid.UUID,
        event_type: str,
        details: str,
        uow: Optional[UnitOfWork] = None,
    ) -> RiskHistoryEntry:
        """Record an immutable history event for a risk record."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        entry = CyberRiskHistory(
            id=uuid.uuid4(),
            risk_id=risk_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
            tenant_id=tenant_id,
            version=1
        )

        async def _save(uow_inst: UnitOfWork) -> None:
            await uow_inst.risk_repo.save_history(entry)

        if uow:
            await _save(uow)
        else:
            async with UnitOfWork() as new_uow:
                await _save(new_uow)
                await new_uow.commit()

        return cls.to_response(entry)

    @classmethod
    def to_response(cls, record: CyberRiskHistory) -> RiskHistoryEntry:
        return RiskHistoryEntry(
            risk_id=record.risk_id,
            timestamp=record.timestamp,
            event_type=record.event_type,
            details=record.details,
        )
