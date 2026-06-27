import uuid
from datetime import datetime, timezone
from typing import Dict, List
from src.domain.entities.exposure import ExposureHistoryEntry


class ExposureHistoryService:
    # in-memory store: exposure_id -> list of history entries
    _history: Dict[uuid.UUID, List[ExposureHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged exposure history."""
        cls._history.clear()

    @classmethod
    def get_history(cls, exposure_id: uuid.UUID) -> List[ExposureHistoryEntry]:
        """Get all logged history for an exposure."""
        return cls._history.get(exposure_id, [])

    @classmethod
    def record_event(
        cls,
        exposure_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> ExposureHistoryEntry:
        """Record an immutable history event for an exposure."""
        entry = ExposureHistoryEntry(
            exposure_id=exposure_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(exposure_id, []).append(entry)
        return entry
