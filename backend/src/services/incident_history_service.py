import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from src.domain.entities.incident import IncidentHistoryEntry
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import IncidentHistory
from src.core.tenant import get_current_tenant_id


class IncidentHistoryService:
    # in-memory store: incident_id -> list of history entries
    _history: Dict[uuid.UUID, List[IncidentHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged history."""
        cls._history.clear()

    @classmethod
    def _add_to_cache(cls, incident_id: uuid.UUID, entry: Any) -> None:
        if incident_id not in cls._history:
            cls._history[incident_id] = []
        
        # Check if already present to avoid duplicates
        exists = False
        t = entry.timestamp if hasattr(entry, "timestamp") else getattr(entry, "created_at", None)
        for h in cls._history[incident_id]:
            if h.event_type == entry.event_type and h.details == entry.details:
                exists = True
                break
        if not exists:
            cls._history[incident_id].append(
                IncidentHistoryEntry(
                    incident_id=incident_id,
                    timestamp=t or datetime.now(timezone.utc),
                    event_type=entry.event_type,
                    details=entry.details,
                )
            )

    @classmethod
    async def get_history(cls, incident_id: uuid.UUID) -> List[IncidentHistoryEntry]:
        """Get all logged history for an incident."""
        async with UnitOfWork() as uow:
            db_histories = await uow.incident_repo.list_history(incident_id)
            res = [
                IncidentHistoryEntry(
                    incident_id=incident_id,
                    timestamp=h.timestamp,
                    event_type=h.event_type,
                    details=h.details,
                )
                for h in db_histories
            ]
            return res

    @classmethod
    async def record_event(
        cls,
        incident_id: uuid.UUID,
        event_type: str,
        details: str,
        uow: Optional[UnitOfWork] = None,
    ) -> IncidentHistoryEntry:
        """Record a history event for an incident. New events are appended and immutable."""
        entry = IncidentHistoryEntry(
            incident_id=incident_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        
        # Warm L2 cache
        if incident_id not in cls._history:
            cls._history[incident_id] = []
        cls._history[incident_id].append(entry)

        # Persist to database
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        
        async def _save(uow_inst: UnitOfWork):
            db_history = IncidentHistory(
                tenant_id=tenant_id,
                incident_id=incident_id,
                event_type=event_type,
                details=details,
                timestamp=entry.timestamp,
            )
            await uow_inst.incident_repo.save_history(db_history)

        if uow:
            await _save(uow)
        else:
            async with UnitOfWork() as new_uow:
                await _save(new_uow)
                await new_uow.commit()

        return entry
