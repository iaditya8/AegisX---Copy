import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.domain.entities.remediation import (
    RemediationHistoryEntry,
    RemediationHistoryType,
)
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import RemediationHistory
from src.core.tenant import get_current_tenant_id


class RemediationHistoryService:
    # in-memory store: remediation_id -> list of history entries
    _history: Dict[uuid.UUID, List[RemediationHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear the in-memory history store."""
        cls._history.clear()

    @classmethod
    async def get_history(cls, remediation_id: uuid.UUID) -> List[RemediationHistoryEntry]:
        """Get the history list for a remediation."""
        async with UnitOfWork() as uow:
            db_entries = await uow.remediation_repo.list_history(remediation_id)
            res = [
                RemediationHistoryEntry(
                    history_id=e.id,
                    remediation_id=e.remediation_id,
                    history_type=RemediationHistoryType(e.history_type),
                    old_value=e.old_value,
                    new_value=e.new_value,
                    actor_id=e.actor_id,
                    timestamp=e.timestamp,
                )
                for e in db_entries
            ]
            return res

    @classmethod
    async def record_event(
        cls,
        remediation_id: uuid.UUID,
        history_type: RemediationHistoryType,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        actor_id: Optional[uuid.UUID] = None,
        uow: Optional[UnitOfWork] = None,
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

        # Warm L2 cache
        if remediation_id not in cls._history:
            cls._history[remediation_id] = []
        cls._history[remediation_id].append(entry)

        # Write to DB
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        async def _save(uow_inst: UnitOfWork):
            db_hist = RemediationHistory(
                tenant_id=tenant_id,
                id=entry.history_id,
                remediation_id=remediation_id,
                history_type=history_type.value,
                old_value=old_value,
                new_value=new_value,
                actor_id=actor_id,
                timestamp=entry.timestamp,
            )
            await uow_inst.remediation_repo.save_history(db_hist)

        if uow:
            await _save(uow)
        else:
            async with UnitOfWork() as new_uow:
                await _save(new_uow)
                await new_uow.commit()

        return entry
