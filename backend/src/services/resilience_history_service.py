from typing import List, Optional
import uuid
from datetime import datetime, timezone
from src.domain.entities.cyber_resilience import ResilienceHistoryEntry
from src.infrastructure.database.models import CyberResilienceHistory
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.core.tenant import get_current_tenant_id


class ResilienceHistoryService:
    @classmethod
    async def clear_history(cls) -> None:
        """Clear all logged resilience history."""
        # No-op in production database to avoid wiping multi-tenant data
        pass

    @classmethod
    async def get_history(cls, resilience_id: uuid.UUID) -> List[ResilienceHistoryEntry]:
        """Get all logged history for a resilience record."""
        async with UnitOfWork() as uow:
            records = await uow.resilience_repo.get_history(resilience_id)
            return [cls.to_response(r) for r in records]

    @classmethod
    async def record_event(
        cls,
        resilience_id: uuid.UUID,
        event_type: str,
        details: str,
        uow: Optional[UnitOfWork] = None,
    ) -> ResilienceHistoryEntry:
        """Record an immutable history event for a resilience record."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        entry = CyberResilienceHistory(
            id=uuid.uuid4(),
            resilience_id=resilience_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details={"message": details},
            tenant_id=tenant_id
        )
        if uow:
            await uow.resilience_repo.save_history(entry)
        else:
            async with UnitOfWork() as uow_new:
                await uow_new.resilience_repo.save_history(entry)
                await uow_new.commit()
        return cls.to_response(entry)

    @classmethod
    def to_response(cls, record: CyberResilienceHistory) -> ResilienceHistoryEntry:
        """Convert a CyberResilienceHistory DB record to ResilienceHistoryEntry response schema."""
        details_str = ""
        if isinstance(record.details, dict):
            details_str = record.details.get("message", "")
        else:
            details_str = str(record.details)
        return ResilienceHistoryEntry(
            resilience_id=record.resilience_id,
            timestamp=record.timestamp,
            event_type=record.event_type,
            details=details_str,
        )
