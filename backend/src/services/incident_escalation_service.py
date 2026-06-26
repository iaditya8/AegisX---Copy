import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.incident import IncidentStatus
from src.services.audit_service import create_audit_entry
from src.services.incident_history_service import IncidentHistoryService
from src.services.incident_service import IncidentService
from src.services.workflow_event_service import WorkflowEventService


class IncidentEscalationService:
    @classmethod
    async def escalate_to_team(
        cls,
        db: AsyncSession,
        incident_id: uuid.UUID,
        team_name: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Escalate incident to a specific security or operations team."""
        incident = IncidentService.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident with ID {incident_id} not found.")

        if incident.status == IncidentStatus.CLOSED:
            raise ValueError("Incident is CLOSED and cannot be escalated.")

        # Transition status to ESCALATED
        await IncidentService.transition_status(
            db, incident_id, IncidentStatus.ESCALATED, actor_id=actor_id
        )

        # Append history log entry
        IncidentHistoryService.record_event(
            incident_id=incident_id,
            event_type="ESCALATED",
            details=f"Incident escalated to team: {team_name}.",
        )

        # Emit incident.escalated event
        await WorkflowEventService.emit_event(
            db=db,
            event_type="incident.escalated",
            payload={
                "incident_id": str(incident_id),
                "escalation_type": "team",
                "team_name": team_name,
            },
        )

        # Audit entry
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="incident.escalate",
            target_type="incident",
            target_id=incident_id,
            metadata={"escalation_type": "team", "team_name": team_name},
        )

    @classmethod
    async def escalate_to_owner(
        cls,
        db: AsyncSession,
        incident_id: uuid.UUID,
        owner_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Escalate incident to the primary owner of the linked assets."""
        incident = IncidentService.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident with ID {incident_id} not found.")

        if incident.status == IncidentStatus.CLOSED:
            raise ValueError("Incident is CLOSED and cannot be escalated.")

        if owner_id:
            incident.owner = owner_id
        else:
            if incident.asset_ids:
                try:
                    from src.infrastructure.database.models import Asset
                    from src.services.scope_service import get_scope_by_id

                    asset = await db.get(Asset, incident.asset_ids[0])
                    if asset and asset.scope_id:
                        scope = await get_scope_by_id(db, asset.scope_id)
                        if scope and scope.owner_id:
                            incident.owner = scope.owner_id
                except Exception:
                    pass

        await IncidentService.transition_status(
            db, incident_id, IncidentStatus.ESCALATED, actor_id=actor_id
        )

        IncidentHistoryService.record_event(
            incident_id=incident_id,
            event_type="ESCALATED",
            details="Incident escalated to asset owner.",
        )

        await WorkflowEventService.emit_event(
            db=db,
            event_type="incident.escalated",
            payload={"incident_id": str(incident_id), "escalation_type": "owner"},
        )

        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="incident.escalate",
            target_type="incident",
            target_id=incident_id,
            metadata={"escalation_type": "owner"},
        )

    @classmethod
    async def escalate_to_management(
        cls,
        db: AsyncSession,
        incident_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Escalate incident to executive management."""
        incident = IncidentService.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident with ID {incident_id} not found.")

        if incident.status == IncidentStatus.CLOSED:
            raise ValueError("Incident is CLOSED and cannot be escalated.")

        await IncidentService.transition_status(
            db, incident_id, IncidentStatus.ESCALATED, actor_id=actor_id
        )

        IncidentHistoryService.record_event(
            incident_id=incident_id,
            event_type="ESCALATED",
            details="Incident escalated to management.",
        )

        await WorkflowEventService.emit_event(
            db=db,
            event_type="incident.escalated",
            payload={
                "incident_id": str(incident_id),
                "escalation_type": "management",
            },
        )

        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="incident.escalate",
            target_type="incident",
            target_id=incident_id,
            metadata={"escalation_type": "management"},
        )

    @classmethod
    async def process_escalations(cls, db: AsyncSession) -> None:
        """Process any automated worker-driven escalations (e.g. on SLA breach)."""
        from src.domain.entities.incident import IncidentSeverity, IncidentStatus

        incidents = IncidentService.get_all_incidents()
        for inc in list(incidents):
            if inc.status in [
                IncidentStatus.CLOSED,
                IncidentStatus.RESOLVED,
                IncidentStatus.ESCALATED,
            ]:
                continue

            age = datetime.now(timezone.utc) - inc.created_at
            if inc.severity == IncidentSeverity.CRITICAL and age > timedelta(hours=1):
                # Transition status to ESCALATED
                await IncidentService.transition_status(
                    db, inc.incident_id, IncidentStatus.ESCALATED
                )
                # Log event in history
                IncidentHistoryService.record_event(
                    incident_id=inc.incident_id,
                    event_type="AUTO_ESCALATED",
                    details="Incident automatically escalated due to SLA breach (CRITICAL severity > 1 hour threshold).",
                )
