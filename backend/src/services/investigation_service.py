import uuid
from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.incident import IncidentStatus, InvestigationEntry
from src.services.incident_history_service import IncidentHistoryService
from src.services.incident_service import IncidentService


class InvestigationService:
    # in-memory store: incident_id -> list of investigation entries
    _investigations: Dict[uuid.UUID, List[InvestigationEntry]] = {}

    @classmethod
    def clear_investigations(cls) -> None:
        """Clear all in-memory investigation logs."""
        cls._investigations.clear()

    @classmethod
    def get_investigation_timeline(
        cls, incident_id: uuid.UUID
    ) -> List[InvestigationEntry]:
        """Get the full sorted timeline of investigation entries for an incident."""
        entries = cls._investigations.get(incident_id, [])
        return sorted(entries, key=lambda x: x.timestamp)

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

        if incident_id not in cls._investigations:
            cls._investigations[incident_id] = []
        cls._investigations[incident_id].append(entry)

        # Log timeline update to history
        IncidentHistoryService.record_event(
            incident_id=incident_id,
            event_type="INVESTIGATION_UPDATED",
            details=f"Investigation started by analyst {analyst_id}: {notes[:50]}",
        )

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

        if incident_id not in cls._investigations:
            cls._investigations[incident_id] = []
        cls._investigations[incident_id].append(entry)

        # Log timeline update to history
        IncidentHistoryService.record_event(
            incident_id=incident_id,
            event_type="INVESTIGATION_UPDATED",
            details=f"Analyst note added by {analyst_id}: {notes[:50]}",
        )

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

        if incident_id not in cls._investigations:
            cls._investigations[incident_id] = []
        cls._investigations[incident_id].append(entry)

        # Log completion to history
        IncidentHistoryService.record_event(
            incident_id=incident_id,
            event_type="INVESTIGATION_UPDATED",
            details=f"Investigation completed by analyst {analyst_id}: {notes[:50]}",
        )

        return entry
