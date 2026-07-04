from typing import List, Optional
import uuid
from datetime import datetime, timezone
from src.domain.entities.security_operations_analytics import AnalyticsHistoryEntry
from src.infrastructure.database.models import SOCAnalyticsHistory
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.core.tenant import get_current_tenant_id


class AnalyticsHistoryService:
    @classmethod
    async def clear_history(cls) -> None:
        """Clear all logged operational analytics history."""
        pass

    @classmethod
    async def get_history(cls, analytics_id: uuid.UUID) -> List[AnalyticsHistoryEntry]:
        """Get all logged history for an analytics record."""
        async with UnitOfWork() as uow:
            records = await uow.soc_repo.get_history(analytics_id)
            return [cls.to_response(r) for r in records]

    @classmethod
    async def record_event(
        cls,
        analytics_id: uuid.UUID,
        event_type: str,
        details: str,
        uow: Optional[UnitOfWork] = None,
    ) -> AnalyticsHistoryEntry:
        """Record an immutable history event for a SOC analytics record."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        entry = SOCAnalyticsHistory(
            id=uuid.uuid4(),
            analytics_id=analytics_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details={"message": details},
            tenant_id=tenant_id
        )
        if uow:
            await uow.soc_repo.save_history(entry)
        else:
            async with UnitOfWork() as uow_new:
                await uow_new.soc_repo.save_history(entry)
                await uow_new.commit()
        return cls.to_response(entry)

    @classmethod
    def to_response(cls, record: SOCAnalyticsHistory) -> AnalyticsHistoryEntry:
        """Convert a SOCAnalyticsHistory DB record to AnalyticsHistoryEntry response schema."""
        details_str = ""
        if isinstance(record.details, dict):
            details_str = record.details.get("message", "")
        else:
            details_str = str(record.details)
        return AnalyticsHistoryEntry(
            analytics_id=record.analytics_id,
            timestamp=record.timestamp,
            event_type=record.event_type,
            details=details_str,
        )
