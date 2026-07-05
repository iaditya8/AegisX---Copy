import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.domain.entities.purple_team import PurpleTeamHistoryEntry
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import PurpleTeamHistory
from src.core.tenant import get_current_tenant_id


class PurpleTeamHistoryService:
    # in-memory store: exercise_id -> list of history entries
    _history: Dict[uuid.UUID, List[PurpleTeamHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged history."""
        cls._history.clear()

    @classmethod
    async def get_history(cls, exercise_id: uuid.UUID) -> List[PurpleTeamHistoryEntry]:
        """Get all logged history for an exercise."""
        async with UnitOfWork() as uow:
            db_entries = await uow.purple_team_repo.list_history(exercise_id)
            res = [
                PurpleTeamHistoryEntry(
                    exercise_id=e.exercise_id,
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
        exercise_id: uuid.UUID,
        event_type: str,
        details: str,
        uow: Optional[UnitOfWork] = None,
    ) -> PurpleTeamHistoryEntry:
        """Record an immutable history event for an exercise."""
        entry = PurpleTeamHistoryEntry(
            exercise_id=exercise_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(exercise_id, []).append(entry)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        async def _save(uow_inst: UnitOfWork):
            db_hist = PurpleTeamHistory(
                tenant_id=tenant_id,
                exercise_id=exercise_id,
                event_type=event_type,
                details=details,
                timestamp=entry.timestamp,
            )
            await uow_inst.purple_team_repo.save_history(db_hist)

        if uow:
            await _save(uow)
        else:
            async with UnitOfWork() as new_uow:
                await _save(new_uow)
                await new_uow.commit()

        return entry
