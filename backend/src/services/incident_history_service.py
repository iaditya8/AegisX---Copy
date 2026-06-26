import uuid
from datetime import datetime, timezone
from typing import Dict, List

from src.domain.entities.incident import IncidentHistoryEntry


class IncidentHistoryService:
    # in-memory store: incident_id -> list of history entries
    _history: Dict[uuid.UUID, List[IncidentHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged history."""
        cls._history.clear()

    @classmethod
    def get_history(cls, incident_id: uuid.UUID) -> List[IncidentHistoryEntry]:
        """Get all logged history for an incident."""
        return cls._history.get(incident_id, [])

    @classmethod
    def record_event(
        cls,
        incident_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> IncidentHistoryEntry:
        """Record a history event for an incident. New events are appended and immutable."""
        entry = IncidentHistoryEntry(
            incident_id=incident_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        if incident_id not in cls._history:
            cls._history[incident_id] = []
        cls._history[incident_id].append(entry)
        return entry
