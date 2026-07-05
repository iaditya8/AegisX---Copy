import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from src.domain.entities.threat_intel import ThreatIntelHistoryEntry
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import ThreatIntelHistory
from src.core.tenant import get_current_tenant_id


class ThreatIntelHistoryService:
    # L2/In-memory cache of history (optional/clear)
    _history: Dict[uuid.UUID, List[ThreatIntelHistoryEntry]] = {}

    @classmethod
    def clear_history(cls) -> None:
        """Clear all GRC threat intelligence history logs."""
        cls._history.clear()

    @classmethod
    async def get_history(cls, threat_intel_id: uuid.UUID) -> tuple:
        """Get all history logs for a GRC threat intelligence record (immutable tuple)."""
        async with UnitOfWork() as uow:
            db_entries = await uow.threat_repo.get_history(threat_intel_id)
            entries = [
                ThreatIntelHistoryEntry(
                    threat_intel_id=e.ioc_id,
                    timestamp=e.timestamp,
                    event_type=e.event_type,
                    details=e.details.get("message", "") if isinstance(e.details, dict) else str(e.details)
                )
                for e in db_entries
            ]
            return tuple(entries)

    @classmethod
    async def record_event(
        cls,
        threat_intel_id: uuid.UUID,
        event_type: str,
        details: str,
        uow: Optional[UnitOfWork] = None,
    ) -> ThreatIntelHistoryEntry:
        """Record an immutable history log for a GRC threat intelligence record."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        
        async def _record(uow_inst: UnitOfWork) -> ThreatIntelHistory:
            history_entry = ThreatIntelHistory(
                tenant_id=tenant_id,
                ioc_id=threat_intel_id,
                event_type=event_type,
                details={"message": details}
            )
            await uow_inst.threat_repo.save_history(history_entry)
            return history_entry

        if uow:
            db_entry = await _record(uow)
        else:
            async with UnitOfWork() as new_uow:
                db_entry = await _record(new_uow)
                await new_uow.commit()

        entry = ThreatIntelHistoryEntry(
            threat_intel_id=threat_intel_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            details=details,
        )
        return entry
