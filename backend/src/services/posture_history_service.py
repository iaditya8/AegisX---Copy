import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List
from src.domain.entities.security_posture import PostureHistoryEntry


class PostureHistoryService:
    # in-memory store: posture_id -> list of history entries
    _history: Dict[uuid.UUID, List[PostureHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged posture history."""
        cls._history.clear()

    @classmethod
    def get_history(cls, posture_id: uuid.UUID) -> List[PostureHistoryEntry]:
        """Get all logged history for a security posture."""
        # Risk Correlation/History Preservation Rule: deepcopied/immutable
        return copy.deepcopy(cls._history.get(posture_id, []))

    @classmethod
    def record_event(
        cls,
        posture_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> PostureHistoryEntry:
        """Record an immutable history event for a security posture."""
        entry = PostureHistoryEntry(
            posture_id=posture_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(posture_id, []).append(entry)
        return entry
