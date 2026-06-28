import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from src.domain.entities.security_intelligence_graph import GraphHistoryEntry


class GraphHistoryService:
    # in-memory store: component_id -> list of history entries
    _history: Dict[uuid.UUID, List[GraphHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all GRC graph history logs."""
        cls._history.clear()

    @classmethod
    def get_history(cls, component_id: uuid.UUID) -> tuple:
        """Get all history logs for a GRC graph component (immutable tuple)."""
        entries = cls._history.get(component_id, [])
        return tuple(copy.deepcopy(entries))

    @classmethod
    def record_event(
        cls,
        component_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> GraphHistoryEntry:
        """Record an immutable history log for a graph node or edge."""
        entry = GraphHistoryEntry(
            component_id=component_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(component_id, []).append(entry)
        return entry
