import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List
from src.domain.entities.security_operations_analytics import AnalyticsHistoryEntry


class AnalyticsHistoryService:
    # in-memory store: analytics_id -> list of history entries
    _history: Dict[uuid.UUID, List[AnalyticsHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged operational analytics history."""
        cls._history.clear()

    @classmethod
    def get_history(cls, analytics_id: uuid.UUID) -> List[AnalyticsHistoryEntry]:
        """Get all logged history for an analytics record."""
        # Immutable deepcopy to prevent callers from modifying history
        return copy.deepcopy(cls._history.get(analytics_id, []))

    @classmethod
    def record_event(
        cls,
        analytics_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> AnalyticsHistoryEntry:
        """Record an immutable history event for a SOC analytics record."""
        entry = AnalyticsHistoryEntry(
            analytics_id=analytics_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(analytics_id, []).append(entry)
        return entry
