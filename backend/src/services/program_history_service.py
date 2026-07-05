import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.domain.entities.security_program import ProgramHistoryEntry
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import SecurityProgramHistory
from src.core.tenant import get_current_tenant_id


class ProgramHistoryService:
    # in-memory store: program_id -> list of history entries
    _history: Dict[uuid.UUID, List[ProgramHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged program history."""
        cls._history.clear()

    @classmethod
    async def get_history(cls, program_id: uuid.UUID) -> List[ProgramHistoryEntry]:
        """Get all logged history for a security program."""
        async with UnitOfWork() as uow:
            db_entries = await uow.program_repo.list_history(program_id)
            res = [
                ProgramHistoryEntry(
                    program_id=e.program_id,
                    timestamp=e.timestamp,
                    event_type=e.event_type,
                    details=e.details,
                )
                for e in db_entries
            ]
            return res

    @classmethod
    async def record_event(
        cls,
        program_id: uuid.UUID,
        event_type: str,
        details: str,
        uow: Optional[UnitOfWork] = None,
    ) -> ProgramHistoryEntry:
        """Record an immutable history event for a security program."""
        entry = ProgramHistoryEntry(
            program_id=program_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(program_id, []).append(entry)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        async def _save(uow_inst: UnitOfWork):
            db_hist = SecurityProgramHistory(
                tenant_id=tenant_id,
                program_id=program_id,
                event_type=event_type,
                details=details,
                timestamp=entry.timestamp,
            )
            await uow_inst.program_repo.save_history(db_hist)

        if uow:
            await _save(uow)
        else:
            async with UnitOfWork() as new_uow:
                await _save(new_uow)
                await new_uow.commit()

        return entry
