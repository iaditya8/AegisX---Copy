import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List
from src.domain.entities.cyber_resilience import ResilienceHistoryEntry


class ResilienceHistoryService:
    # in-memory store: resilience_id -> list of history entries
    _history: Dict[uuid.UUID, List[ResilienceHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged resilience history."""
        cls._history.clear()

    @classmethod
    def get_history(cls, resilience_id: uuid.UUID) -> List[ResilienceHistoryEntry]:
        """Get all logged history for a resilience record."""
        # Immutable deepcopy to prevent callers from modifying history
        return copy.deepcopy(cls._history.get(resilience_id, []))

    @classmethod
    def record_event(
        cls,
        resilience_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> ResilienceHistoryEntry:
        """Record an immutable history event for a resilience record."""
        entry = ResilienceHistoryEntry(
            resilience_id=resilience_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(resilience_id, []).append(entry)
        return entry
