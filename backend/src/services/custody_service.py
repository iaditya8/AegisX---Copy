import uuid
from datetime import datetime, timezone
from typing import Dict, List

from src.domain.entities.case import ChainOfCustodyAction, ChainOfCustodyEntry


class CustodyService:
    # in-memory store: evidence_id -> list of ChainOfCustodyEntry
    _custody: Dict[uuid.UUID, List[ChainOfCustodyEntry]] = {}

    @classmethod
    def clear_custody(cls) -> None:
        """Clear all in-memory custody entries."""
        cls._custody.clear()

    @classmethod
    def get_custody(cls, evidence_id: uuid.UUID) -> List[ChainOfCustodyEntry]:
        """Retrieve custody chain for an evidence ID."""
        return cls._custody.get(evidence_id, [])

    @classmethod
    def record_custody_event(
        cls,
        evidence_id: uuid.UUID,
        action: ChainOfCustodyAction,
        actor: uuid.UUID,
        notes: str,
        integrity_verified: bool,
    ) -> ChainOfCustodyEntry:
        """Record a custody action entry in the chain."""
        entry = ChainOfCustodyEntry(
            entry_id=uuid.uuid4(),
            evidence_id=evidence_id,
            action=action,
            actor=actor,
            timestamp=datetime.now(timezone.utc),
            notes=notes,
            integrity_verified=integrity_verified,
        )
        cls._custody.setdefault(evidence_id, []).append(entry)
        return entry
