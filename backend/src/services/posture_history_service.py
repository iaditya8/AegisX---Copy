import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.domain.entities.security_posture import PostureHistoryEntry
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import SecurityPostureHistory
from src.core.tenant import get_current_tenant_id


class PostureHistoryService:
    # in-memory store: posture_id -> list of history entries
    _history: Dict[uuid.UUID, List[PostureHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all logged posture history."""
        cls._history.clear()

    @classmethod
    async def get_history(cls, posture_id: uuid.UUID) -> List[PostureHistoryEntry]:
        """Get all logged history for a security posture."""
        async with UnitOfWork() as uow:
            db_entries = await uow.posture_repo.list_history(posture_id)
            res = [
                PostureHistoryEntry(
                    posture_id=e.posture_id,
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
        posture_id: uuid.UUID,
        event_type: str,
        details: str,
        uow: Optional[UnitOfWork] = None,
    ) -> PostureHistoryEntry:
        """Record an immutable history event for a security posture."""
        entry = PostureHistoryEntry(
            posture_id=posture_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        cls._history.setdefault(posture_id, []).append(entry)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        async def _save(uow_inst: UnitOfWork):
            db_hist = SecurityPostureHistory(
                tenant_id=tenant_id,
                posture_id=posture_id,
                event_type=event_type,
                details=details,
                timestamp=entry.timestamp,
            )
            await uow_inst.posture_repo.save_history(db_hist)

        if uow:
            await _save(uow)
        else:
            async with UnitOfWork() as new_uow:
                await _save(new_uow)
                await new_uow.commit()

        return entry
