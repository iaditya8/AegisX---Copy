import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List
from src.domain.entities.security_program import ProgramHistoryEntry


class ProgramHistoryService:
    # in-memory store: program_id -> list of history entries
    _history: Dict[uuid.UUID, List[ProgramHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged program history."""
        cls._history.clear()

    @classmethod
    def get_history(cls, program_id: uuid.UUID) -> List[ProgramHistoryEntry]:
        """Get all logged history for a security program."""
        # Immutable deepcopy
        return copy.deepcopy(cls._history.get(program_id, []))

    @classmethod
    def record_event(
        cls,
        program_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> ProgramHistoryEntry:
        """Record an immutable history event for a security program."""
        entry = ProgramHistoryEntry(
            program_id=program_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(program_id, []).append(entry)
        return entry
