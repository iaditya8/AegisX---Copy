import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List
from src.domain.entities.cyber_risk_quantification import RiskHistoryEntry


class QuantifiedRiskHistoryService:
    # in-memory store: risk_id -> list of history entries
    _history: Dict[uuid.UUID, List[RiskHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged operational risk history."""
        cls._history.clear()

    @classmethod
    def get_history(cls, risk_id: uuid.UUID) -> List[RiskHistoryEntry]:
        """Get all logged history for a risk record."""
        # Immutable deepcopy to prevent callers from modifying history
        return copy.deepcopy(cls._history.get(risk_id, []))

    @classmethod
    def record_event(
        cls,
        risk_id: uuid.UUID,
        event_type: str,
        details: str,
    ) -> RiskHistoryEntry:
        """Record an immutable history event for a risk record."""
        entry = RiskHistoryEntry(
            risk_id=risk_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(risk_id, []).append(entry)
        return entry
