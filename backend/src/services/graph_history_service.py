import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from src.domain.entities.security_intelligence_graph import GraphHistoryEntry
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import SecurityIntelligenceGraphHistory
from src.core.tenant import get_current_tenant_id


class GraphHistoryService:
    # L2 cache of history
    _history: Dict[uuid.UUID, List[GraphHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all GRC graph history logs."""
        cls._history.clear()

    @classmethod
    async def get_history(cls, component_id: uuid.UUID) -> tuple:
        """Get all history logs for a GRC graph component (immutable tuple)."""
        async with UnitOfWork() as uow:
            db_entries = await uow.graph_repo.get_history(component_id)
            entries = [
                GraphHistoryEntry(
                    component_id=e.component_id,
                    timestamp=e.created_at,
                    event_type=e.event_type,
                    details=e.details
                )
                for e in db_entries
            ]
            return tuple(entries)

    @classmethod
    async def record_event(
        cls,
        component_id: uuid.UUID,
        event_type: str,
        details: str,
        uow: Optional[UnitOfWork] = None,
    ) -> GraphHistoryEntry:
        """Record an immutable history log for a graph node or edge."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        
        async def _record(uow_inst: UnitOfWork) -> SecurityIntelligenceGraphHistory:
            history_entry = SecurityIntelligenceGraphHistory(
                tenant_id=tenant_id,
                component_id=component_id,
                event_type=event_type,
                details=details
            )
            await uow_inst.graph_repo.save_history(history_entry)
            return history_entry

        if uow:
            db_entry = await _record(uow)
        else:
            async with UnitOfWork() as new_uow:
                db_entry = await _record(new_uow)
                await new_uow.commit()

        entry = GraphHistoryEntry(
            component_id=component_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        return entry
