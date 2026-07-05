import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.domain.entities.security_decision import DecisionHistoryEntry
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import SecurityDecisionHistory
from src.core.tenant import get_current_tenant_id


class DecisionHistoryService:
    # in-memory store: decision_id -> list of history entries
    _history: Dict[uuid.UUID, List[DecisionHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all decision history logs."""
        cls._history.clear()

    @classmethod
    async def get_history(cls, decision_id: uuid.UUID) -> tuple:
        """Get all history logs for a decision (immutable tuple)."""
        async with UnitOfWork() as uow:
            db_entries = await uow.decision_repo.list_history(decision_id)
            res = [
                DecisionHistoryEntry(
                    decision_id=e.decision_id,
                    timestamp=e.timestamp,
                    event_type=e.event_type,
                    details=e.details,
                )
                for e in db_entries
            ]
            return tuple(res)

    @classmethod
    async def record_event(
        cls,
        decision_id: uuid.UUID,
        event_type: str,
        details: str,
        uow: Optional[UnitOfWork] = None,
    ) -> DecisionHistoryEntry:
        """Record an immutable history log for a decision."""
        entry = DecisionHistoryEntry(
            decision_id=decision_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(decision_id, []).append(entry)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        async def _save(uow_inst: UnitOfWork):
            db_hist = SecurityDecisionHistory(
                tenant_id=tenant_id,
                decision_id=decision_id,
                event_type=event_type,
                details=details,
                timestamp=entry.timestamp,
            )
            await uow_inst.decision_repo.save_history(db_hist)

        if uow:
            await _save(uow)
        else:
            async with UnitOfWork() as new_uow:
                await _save(new_uow)
                await new_uow.commit()

        return entry
