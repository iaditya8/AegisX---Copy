import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List
from src.domain.entities.threat_intel import ThreatIntelHistoryEntry


class ThreatIntelHistoryService:
    # in-memory store: threat_intel_id -> list of history entries
    _history: Dict[uuid.UUID, List[ThreatIntelHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all GRC threat intelligence history logs."""
        cls._history.clear()

    @classmethod
    def get_history(cls, threat_intel_id: uuid.UUID) -> tuple:
        """Get all history logs for a GRC threat intelligence record (immutable tuple)."""
        # Immutable tuple to prevent callers from modifying history
        return tuple(copy.deepcopy(cls._history.get(threat_intel_id, [])))

    @classmethod
    def record_event(
        cls,
        threat_intel_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> ThreatIntelHistoryEntry:
        """Record an immutable history log for a GRC threat intelligence record."""
        entry = ThreatIntelHistoryEntry(
            threat_intel_id=threat_intel_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(threat_intel_id, []).append(entry)
        return entry
