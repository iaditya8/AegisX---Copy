import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List

from src.domain.entities.autonomous_planning import PlanningHistoryEntry


class PlanningHistoryService:
    # in-memory store: plan_id -> list of history entries
    _history: Dict[uuid.UUID, List[PlanningHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all history logs."""
        cls._history.clear()

    @classmethod
    def get_history(cls, plan_id: uuid.UUID) -> tuple:
        """Get all history logs for a plan (immutable tuple)."""
        entries = cls._history.get(plan_id, [])
        return tuple(copy.deepcopy(entries))

    @classmethod
    def record_event(
        cls,
        plan_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> PlanningHistoryEntry:
        """Record an immutable history log for a plan."""
        entry = PlanningHistoryEntry(
            plan_id=plan_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(plan_id, []).append(entry)
        return entry
