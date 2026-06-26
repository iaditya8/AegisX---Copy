import uuid
from datetime import datetime, timezone
from typing import Dict, List

from src.domain.entities.case import CaseHistoryEntry


class CaseHistoryService:
    # in-memory store: case_id -> list of history entries
    _history: Dict[uuid.UUID, List[CaseHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged history."""
        cls._history.clear()

    @classmethod
    def get_history(cls, case_id: uuid.UUID) -> List[CaseHistoryEntry]:
        """Get all logged history for a case."""
        return cls._history.get(case_id, [])

    @classmethod
    def record_event(
        cls,
        case_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> CaseHistoryEntry:
        """Record a history event for a case. Entries are immutable and appended to the history."""
        entry = CaseHistoryEntry(
            case_id=case_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(case_id, []).append(entry)
        return entry
