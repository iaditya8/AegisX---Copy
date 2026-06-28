import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List

from src.domain.entities.security_intelligence_fabric import FabricHistoryEntry


class FabricHistoryService:
    # in-memory store: fabric_id -> list of history entries
    _history: Dict[uuid.UUID, List[FabricHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all history logs."""
        cls._history.clear()

    @classmethod
    def get_history(cls, fabric_id: uuid.UUID) -> tuple:
        """Get all history logs for a fabric node (immutable tuple)."""
        entries = cls._history.get(fabric_id, [])
        return tuple(copy.deepcopy(entries))

    @classmethod
    def record_event(
        cls,
        fabric_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> FabricHistoryEntry:
        """Record an immutable history log for a fabric node."""
        entry = FabricHistoryEntry(
            fabric_id=fabric_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(fabric_id, []).append(entry)
        return entry
