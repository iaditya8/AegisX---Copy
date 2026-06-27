import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List
from src.domain.entities.control_validation import ControlHistoryEntry


class ControlHistoryService:
    # in-memory store: control_id -> list of history entries
    _history: Dict[uuid.UUID, List[ControlHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged control history."""
        cls._history.clear()

    @classmethod
    def get_history(cls, control_id: uuid.UUID) -> List[ControlHistoryEntry]:
        """Get all logged history for a security control."""
        # Immutable deepcopy
        return copy.deepcopy(cls._history.get(control_id, []))

    @classmethod
    def record_event(
        cls,
        control_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> ControlHistoryEntry:
        """Record an immutable history event for a control."""
        entry = ControlHistoryEntry(
            control_id=control_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(control_id, []).append(entry)
        return entry
