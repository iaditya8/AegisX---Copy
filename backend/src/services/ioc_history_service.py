import uuid
from datetime import datetime, timezone
from typing import Dict, List

from src.domain.entities.threat_intelligence import IOCHistoryEntry


class IOCHistoryService:
    # in-memory store: ioc_id -> list of history entries
    _history: Dict[uuid.UUID, List[IOCHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged history."""
        cls._history.clear()

    @classmethod
    def get_history(cls, ioc_id: uuid.UUID) -> List[IOCHistoryEntry]:
        """Get all logged history for an IOC."""
        return cls._history.get(ioc_id, [])

    @classmethod
    def record_event(
        cls,
        ioc_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> IOCHistoryEntry:
        """Record a history event for an IOC."""
        entry = IOCHistoryEntry(
            ioc_id=ioc_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(ioc_id, []).append(entry)
        return entry
