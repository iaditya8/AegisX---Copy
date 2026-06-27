import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List
from src.domain.entities.governance_risk_compliance import ComplianceHistoryEntry


class ComplianceHistoryService:
    # in-memory store: assessment_id -> list of history entries
    _history: Dict[uuid.UUID, List[ComplianceHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all GRC history logs."""
        cls._history.clear()

    @classmethod
    def get_history(cls, assessment_id: uuid.UUID) -> List[ComplianceHistoryEntry]:
        """Get all history logs for a GRC assessment."""
        # Immutable deepcopy to prevent callers from modifying history
        return copy.deepcopy(cls._history.get(assessment_id, []))

    @classmethod
    def record_event(
        cls,
        assessment_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> ComplianceHistoryEntry:
        """Record an immutable history log for a GRC assessment."""
        entry = ComplianceHistoryEntry(
            assessment_id=assessment_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(assessment_id, []).append(entry)
        return entry
