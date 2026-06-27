import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List
from src.domain.entities.executive_reporting import ExecutiveHistoryEntry


class ExecutiveHistoryService:
    # in-memory store: report_id -> list of history entries
    _history: Dict[uuid.UUID, List[ExecutiveHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged report history."""
        cls._history.clear()

    @classmethod
    def get_history(cls, report_id: uuid.UUID) -> List[ExecutiveHistoryEntry]:
        """Get all logged history for an executive report."""
        # Immutable deepcopy to prevent callers from modifying history
        return copy.deepcopy(cls._history.get(report_id, []))

    @classmethod
    def record_event(
        cls,
        report_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> ExecutiveHistoryEntry:
        """Record an immutable history event for a report."""
        entry = ExecutiveHistoryEntry(
            report_id=report_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(report_id, []).append(entry)
        return entry
