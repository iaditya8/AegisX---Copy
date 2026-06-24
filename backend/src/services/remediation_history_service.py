import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.domain.entities.remediation import (
    RemediationHistoryEntry,
    RemediationHistoryType,
)


class RemediationHistoryService:
    # in-memory store: remediation_id -> list of history entries
    _history: Dict[uuid.UUID, List[RemediationHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear the in-memory history store."""
        cls._history.clear()

    @classmethod
    def get_history(cls, remediation_id: uuid.UUID) -> List[RemediationHistoryEntry]:
        """Get the history list for a remediation."""
        return cls._history.get(remediation_id, [])

    @classmethod
    def record_event(
        cls,
        remediation_id: uuid.UUID,
        history_type: RemediationHistoryType,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> RemediationHistoryEntry:
        """Record a history event for a remediation."""
        entry = RemediationHistoryEntry(
            history_id=uuid.uuid4(),
            remediation_id=remediation_id,
            history_type=history_type,
            old_value=old_value,
            new_value=new_value,
            actor_id=actor_id,
            timestamp=datetime.now(timezone.utc),
        )
        if remediation_id not in cls._history:
            cls._history[remediation_id] = []
        cls._history[remediation_id].append(entry)
        return entry
