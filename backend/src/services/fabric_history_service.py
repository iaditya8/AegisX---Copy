import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.domain.entities.security_intelligence_fabric import FabricHistoryEntry
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import SecurityIntelligenceFabricHistory
from src.core.tenant import get_current_tenant_id


class FabricHistoryService:
    # in-memory store: fabric_id -> list of history entries
    _history: Dict[uuid.UUID, List[FabricHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all history logs."""
        cls._history.clear()

    @classmethod
    async def get_history(cls, fabric_id: uuid.UUID) -> tuple:
        """Get all history logs for a fabric node (immutable tuple)."""
        async with UnitOfWork() as uow:
            db_entries = await uow.fabric_repo.list_history(fabric_id)
            res = [
                FabricHistoryEntry(
                    fabric_id=e.fabric_id,
                    timestamp=e.timestamp,
                    event_type=e.event_type,
                    details=e.details,
                )
                for e in db_entries
            ]
            return tuple(res)

    @classmethod
    async def record_event(
        cls,
        fabric_id: uuid.UUID,
        event_type: str,
        details: str,
        uow: Optional[UnitOfWork] = None,
    ) -> FabricHistoryEntry:
        """Record an immutable history log for a fabric node."""
        entry = FabricHistoryEntry(
            fabric_id=fabric_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(fabric_id, []).append(entry)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        async def _save(uow_inst: UnitOfWork):
            db_hist = SecurityIntelligenceFabricHistory(
                tenant_id=tenant_id,
                fabric_id=fabric_id,
                event_type=event_type,
                details=details,
                timestamp=entry.timestamp,
            )
            await uow_inst.fabric_repo.save_history(db_hist)

        if uow:
            await _save(uow)
        else:
            async with UnitOfWork() as new_uow:
                await _save(new_uow)
                await new_uow.commit()

        return entry
