import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List

from src.domain.entities.security_decision import DecisionHistoryEntry


class DecisionHistoryService:
    # in-memory store: decision_id -> list of history entries
    _history: Dict[uuid.UUID, List[DecisionHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all decision history logs."""
        cls._history.clear()

    @classmethod
    def get_history(cls, decision_id: uuid.UUID) -> tuple:
        """Get all history logs for a decision (immutable tuple)."""
        entries = cls._history.get(decision_id, [])
        return tuple(copy.deepcopy(entries))

    @classmethod
    def record_event(
        cls,
        decision_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> DecisionHistoryEntry:
        """Record an immutable history log for a decision."""
        entry = DecisionHistoryEntry(
            decision_id=decision_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(decision_id, []).append(entry)
        return entry
