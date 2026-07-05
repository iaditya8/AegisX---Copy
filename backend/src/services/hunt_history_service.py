import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.domain.entities.hunt import HuntHistoryEntry
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import HuntHistory
from src.core.tenant import get_current_tenant_id


class HuntHistoryService:
    # in-memory store: hunt_id -> list of history entries
    _history: Dict[uuid.UUID, List[HuntHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged history."""
        cls._history.clear()

    @classmethod
    async def get_history(cls, hunt_id: uuid.UUID) -> List[HuntHistoryEntry]:
        """Get all logged history for a hunt."""
        async with UnitOfWork() as uow:
            db_entries = await uow.hunt_repo.list_history(hunt_id)
            res = [
                HuntHistoryEntry(
                    hunt_id=e.hunt_id,
                    timestamp=e.timestamp,
                    event_type=e.event_type,
                    details=e.details,
                )
                for e in db_entries
            ]
            return res

    @classmethod
    async def record_event(
        cls,
        hunt_id: uuid.UUID,
        event_type: str,
        details: str,
        uow: Optional[UnitOfWork] = None,
    ) -> HuntHistoryEntry:
        """Record an immutable history event for a hunt."""
        entry = HuntHistoryEntry(
            hunt_id=hunt_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(hunt_id, []).append(entry)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        async def _save(uow_inst: UnitOfWork):
            db_hist = HuntHistory(
                tenant_id=tenant_id,
                hunt_id=hunt_id,
                event_type=event_type,
                details=details,
                timestamp=entry.timestamp,
            )
            await uow_inst.hunt_repo.save_history(db_hist)

        if uow:
            await _save(uow)
        else:
            async with UnitOfWork() as new_uow:
                await _save(new_uow)
                await new_uow.commit()

        return entry
