import uuid
from datetime import datetime, timezone
from typing import Dict, List

from src.domain.entities.hunt import HuntHistoryEntry


class HuntHistoryService:
    # in-memory store: hunt_id -> list of history entries
    _history: Dict[uuid.UUID, List[HuntHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged history."""
        cls._history.clear()

    @classmethod
    def get_history(cls, hunt_id: uuid.UUID) -> List[HuntHistoryEntry]:
        """Get all logged history for a hunt."""
        return cls._history.get(hunt_id, [])

    @classmethod
    def record_event(
        cls,
        hunt_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> HuntHistoryEntry:
        """Record an immutable history event for a hunt."""
        entry = HuntHistoryEntry(
            hunt_id=hunt_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(hunt_id, []).append(entry)
        return entry
