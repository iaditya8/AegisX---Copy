import uuid
from datetime import datetime, timezone
from typing import Dict, List

from src.domain.entities.detection import DetectionHistoryEntry


class DetectionHistoryService:
    # in-memory store: detection_id -> list of history entries
    _history: Dict[uuid.UUID, List[DetectionHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged history."""
        cls._history.clear()

    @classmethod
    def get_history(cls, detection_id: uuid.UUID) -> List[DetectionHistoryEntry]:
        """Get all logged history for a detection."""
        return cls._history.get(detection_id, [])

    @classmethod
    def record_event(
        cls,
        detection_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> DetectionHistoryEntry:
        """Record a history event for a detection."""
        entry = DetectionHistoryEntry(
            detection_id=detection_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(detection_id, []).append(entry)
        return entry
