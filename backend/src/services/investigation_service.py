import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.incident import IncidentStatus, InvestigationEntry
from src.services.incident_history_service import IncidentHistoryService
from src.services.incident_service import IncidentService
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import IncidentInvestigation
from src.core.tenant import get_current_tenant_id


class InvestigationService:
    # in-memory store/cache: incident_id -> list of investigation entries
    _investigations: Dict[uuid.UUID, List[InvestigationEntry]] = {}

    @classmethod
    def clear_investigations(cls) -> None:
        """Clear all in-memory investigation logs."""
        cls._investigations.clear()

    @classmethod
    def _add_to_cache(cls, incident_id: uuid.UUID, entry: Any) -> None:
        if incident_id not in cls._investigations:
            cls._investigations[incident_id] = []
        
        t = entry.timestamp if hasattr(entry, "timestamp") else getattr(entry, "created_at", None)
        eid = entry.entry_id if hasattr(entry, "entry_id") else getattr(entry, "id", uuid.uuid4())
        
        # Avoid duplicate entries in cache
        exists = False
        for inv in cls._investigations[incident_id]:
            if inv.entry_id == eid:
                exists = True
                break
        if not exists:
            cls._investigations[incident_id].append(
                InvestigationEntry(
                    entry_id=eid,
                    incident_id=incident_id,
                    timestamp=t or datetime.now(timezone.utc),
                    analyst=entry.analyst,
                    action=entry.action,
                    notes=entry.notes,
                )
            )

    @classmethod
    async def get_investigation_timeline(
        cls, incident_id: uuid.UUID
    ) -> List[InvestigationEntry]:
        """Get the full sorted timeline of investigation entries for an incident."""
        async with UnitOfWork() as uow:
            db_entries = await uow.incident_repo.list_investigations(incident_id)
            res = [
                InvestigationEntry(
                    entry_id=e.entry_id,
                    incident_id=e.incident_id,
                    timestamp=e.timestamp,
                    analyst=e.analyst,
                    action=e.action,
                    notes=e.notes,
                )
                for e in db_entries
            ]
            return sorted(res, key=lambda x: x.timestamp)

    @classmethod
    async def start_investigation(
        cls,
        db: AsyncSession,
        incident_id: uuid.UUID,
        analyst_id: uuid.UUID,
        notes: str,
    ) -> InvestigationEntry:
        """Start an investigation on an incident."""
        incident = IncidentService.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident with ID {incident_id} not found.")

        if incident.status == IncidentStatus.CLOSED:
            raise ValueError("Incident is CLOSED and cannot be mutated.")

        # Transition status to INVESTIGATING if valid and not already there
        if incident.status != IncidentStatus.INVESTIGATING:
            await IncidentService.transition_status(
                db, incident_id, IncidentStatus.INVESTIGATING, actor_id=analyst_id
            )

        entry = InvestigationEntry(
            entry_id=uuid.uuid4(),
            incident_id=incident_id,
            timestamp=datetime.now(timezone.utc),
            analyst=analyst_id,
            action="START",
            notes=notes,
        )

        # Warm cache
        if incident_id not in cls._investigations:
            cls._investigations[incident_id] = []
        cls._investigations[incident_id].append(entry)

        # Write to DB
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_entry = IncidentInvestigation(
                tenant_id=tenant_id,
                entry_id=entry.entry_id,
                incident_id=incident_id,
                timestamp=entry.timestamp,
                analyst=analyst_id,
                action="START",
                notes=notes,
            )
            await uow.incident_repo.save_investigation(db_entry)
            
            # Log timeline update to history
            await IncidentHistoryService.record_event(
                incident_id=incident_id,
                event_type="INVESTIGATION_UPDATED",
                details=f"Investigation started by analyst {analyst_id}: {notes[:50]}",
                uow=uow,
            )
            await uow.commit()

        return entry

    @classmethod
    async def add_investigation_note(
        cls,
        db: AsyncSession,
        incident_id: uuid.UUID,
        analyst_id: uuid.UUID,
        notes: str,
    ) -> InvestigationEntry:
        """Add an analyst note to the investigation timeline."""
        incident = IncidentService.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident with ID {incident_id} not found.")

        if incident.status == IncidentStatus.CLOSED:
            raise ValueError("Incident is CLOSED and cannot be mutated.")

        entry = InvestigationEntry(
            entry_id=uuid.uuid4(),
            incident_id=incident_id,
            timestamp=datetime.now(timezone.utc),
            analyst=analyst_id,
            action="NOTE",
            notes=notes,
        )

        # Warm cache
        if incident_id not in cls._investigations:
            cls._investigations[incident_id] = []
        cls._investigations[incident_id].append(entry)

        # Write to DB
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_entry = IncidentInvestigation(
                tenant_id=tenant_id,
                entry_id=entry.entry_id,
                incident_id=incident_id,
                timestamp=entry.timestamp,
                analyst=analyst_id,
                action="NOTE",
                notes=notes,
            )
            await uow.incident_repo.save_investigation(db_entry)
            
            # Log timeline update to history
            await IncidentHistoryService.record_event(
                incident_id=incident_id,
                event_type="INVESTIGATION_UPDATED",
                details=f"Analyst note added by {analyst_id}: {notes[:50]}",
                uow=uow,
            )
            await uow.commit()

        return entry

    @classmethod
    async def complete_investigation(
        cls,
        db: AsyncSession,
        incident_id: uuid.UUID,
        analyst_id: uuid.UUID,
        notes: str,
    ) -> InvestigationEntry:
        """Complete the investigation and move incident to CONTAINED status."""
        incident = IncidentService.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident with ID {incident_id} not found.")

        if incident.status == IncidentStatus.CLOSED:
            raise ValueError("Incident is CLOSED and cannot be mutated.")

        # Transition status to CONTAINED
        await IncidentService.transition_status(
            db, incident_id, IncidentStatus.CONTAINED, actor_id=analyst_id
        )

        entry = InvestigationEntry(
            entry_id=uuid.uuid4(),
            incident_id=incident_id,
            timestamp=datetime.now(timezone.utc),
            analyst=analyst_id,
            action="COMPLETE",
            notes=notes,
        )

        # Warm cache
        if incident_id not in cls._investigations:
            cls._investigations[incident_id] = []
        cls._investigations[incident_id].append(entry)

        # Write to DB
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_entry = IncidentInvestigation(
                tenant_id=tenant_id,
                entry_id=entry.entry_id,
                incident_id=incident_id,
                timestamp=entry.timestamp,
                analyst=analyst_id,
                action="COMPLETE",
                notes=notes,
            )
            await uow.incident_repo.save_investigation(db_entry)
            
            # Log completion to history
            await IncidentHistoryService.record_event(
                incident_id=incident_id,
                event_type="INVESTIGATION_UPDATED",
                details=f"Investigation completed by analyst {analyst_id}: {notes[:50]}",
                uow=uow,
                )
            await uow.commit()

        return entry
