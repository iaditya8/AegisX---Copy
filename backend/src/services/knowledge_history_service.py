import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List
from src.domain.entities.security_knowledge import KnowledgeHistoryEntry


class KnowledgeHistoryService:
    # in-memory store: knowledge_id -> list of history entries
    _history: Dict[uuid.UUID, List[KnowledgeHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all GRC knowledge history logs."""
        cls._history.clear()

    @classmethod
    def get_history(cls, knowledge_id: uuid.UUID) -> List[KnowledgeHistoryEntry]:
        """Get all history logs for a GRC knowledge record."""
        # Immutable deepcopy to prevent callers from modifying history
        return copy.deepcopy(cls._history.get(knowledge_id, []))

    @classmethod
    def record_event(
        cls,
        knowledge_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> KnowledgeHistoryEntry:
        """Record an immutable history log for a GRC knowledge record."""
        entry = KnowledgeHistoryEntry(
            knowledge_id=knowledge_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(knowledge_id, []).append(entry)
        return entry
