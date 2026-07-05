import uuid
from datetime import datetime, timezone
from typing import List, Optional
from src.domain.entities.security_knowledge import KnowledgeHistoryEntry
from src.infrastructure.database.models import SecurityKnowledgeHistory
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.core.tenant import get_current_tenant_id


class KnowledgeHistoryService:
    @classmethod
    async def clear_history(cls) -> None:
        """Clear all GRC knowledge history logs."""
        pass

    @classmethod
    async def get_history(cls, knowledge_id: uuid.UUID) -> List[KnowledgeHistoryEntry]:
        """Get all history logs for a GRC knowledge record."""
        async with UnitOfWork() as uow:
            records = await uow.knowledge_repo.get_history(knowledge_id)
            return [cls.to_response(r) for r in records]

    @classmethod
    async def record_event(
        cls,
        knowledge_id: uuid.UUID,
        event_type: str,
        details: str,
        uow: Optional[UnitOfWork] = None,
    ) -> KnowledgeHistoryEntry:
        """Record an immutable history log for a GRC knowledge record."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        entry = SecurityKnowledgeHistory(
            id=uuid.uuid4(),
            knowledge_id=knowledge_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
            tenant_id=tenant_id,
            version=1
        )

        async def _save(uow_inst: UnitOfWork) -> None:
            await uow_inst.knowledge_repo.save_history(entry)

        if uow:
            await _save(uow)
        else:
            async with UnitOfWork() as new_uow:
                await _save(new_uow)
                await new_uow.commit()

        return cls.to_response(entry)

    @classmethod
    def to_response(cls, record: SecurityKnowledgeHistory) -> KnowledgeHistoryEntry:
        return KnowledgeHistoryEntry(
            knowledge_id=record.knowledge_id,
            timestamp=record.timestamp,
            event_type=record.event_type,
            details=record.details,
        )
