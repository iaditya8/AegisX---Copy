import uuid
from datetime import datetime, timezone
from typing import Dict, List
from src.domain.entities.purple_team import PurpleTeamHistoryEntry


class PurpleTeamHistoryService:
    # in-memory store: exercise_id -> list of history entries
    _history: Dict[uuid.UUID, List[PurpleTeamHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged history."""
        cls._history.clear()

    @classmethod
    def get_history(cls, exercise_id: uuid.UUID) -> List[PurpleTeamHistoryEntry]:
        """Get all logged history for an exercise."""
        return cls._history.get(exercise_id, [])

    @classmethod
    def record_event(
        cls,
        exercise_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> PurpleTeamHistoryEntry:
        """Record an immutable history event for an exercise."""
        entry = PurpleTeamHistoryEntry(
            exercise_id=exercise_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(exercise_id, []).append(entry)
        return entry
