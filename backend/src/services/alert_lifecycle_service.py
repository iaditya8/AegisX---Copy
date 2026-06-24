import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.alert import AlertSeverity, AlertStatus, AlertType
from src.services.audit_service import create_audit_entry
from src.services.workflow_event_service import WorkflowEventService


class AlertRecord:
    def __init__(
        self,
        alert_id: uuid.UUID,
        alert_fingerprint: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        status: AlertStatus,
        title: str,
        description: str,
        asset_id: Optional[uuid.UUID] = None,
        finding_id: Optional[uuid.UUID] = None,
        recommendation_id: Optional[uuid.UUID] = None,
        remediation_id: Optional[uuid.UUID] = None,
        owner: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.alert_id = alert_id
        self.alert_fingerprint = alert_fingerprint
        self.alert_type = alert_type
        self.severity = severity
        self.status = status
        self.title = title
        self.description = description
        self.asset_id = asset_id
        self.finding_id = finding_id
        self.recommendation_id = recommendation_id
        self.remediation_id = remediation_id
        self.owner = owner
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
        self.history = []
        self.escalation_history = []


class AlertLifecycleService:
    # in-memory store: alert_id -> AlertRecord
    _alerts: Dict[uuid.UUID, AlertRecord] = {}
    # fingerprint lookup: fingerprint -> alert_id
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def get_all_alerts(cls) -> List[AlertRecord]:
        """Return all alert records."""
        return list(cls._alerts.values())

    @classmethod
    def get_alert(cls, alert_id: uuid.UUID) -> Optional[AlertRecord]:
        """Retrieve a specific alert record."""
        return cls._alerts.get(alert_id)

    @classmethod
    def get_alert_by_fingerprint(cls, fingerprint: str) -> Optional[AlertRecord]:
        """Retrieve alert by fingerprint."""
        aid = cls._fingerprint_lookup.get(fingerprint)
        if aid:
            return cls.get_alert(aid)
        return None

    @classmethod
    def clear_alerts(cls) -> None:
        """Clear all in-memory alerts."""
        cls._alerts.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def validate_transition(
        cls, old_status: AlertStatus, new_status: AlertStatus
    ) -> None:
        """Enforce strict alert state machine transitions."""
        if old_status == new_status:
            return

        if old_status in [AlertStatus.RESOLVED, AlertStatus.SUPPRESSED]:
            raise ValueError(
                f"Cannot transition from terminal state {old_status.value}"
            )

        if old_status == AlertStatus.OPEN:
            if new_status not in [
                AlertStatus.ACKNOWLEDGED,
                AlertStatus.SUPPRESSED,
                AlertStatus.RESOLVED,
            ]:
                raise ValueError(
                    f"Invalid transition from {old_status.value} to {new_status.value}"
                )

        elif old_status == AlertStatus.ACKNOWLEDGED:
            if new_status not in [AlertStatus.IN_PROGRESS, AlertStatus.RESOLVED]:
                raise ValueError(
                    f"Invalid transition from {old_status.value} to {new_status.value}"
                )

        elif old_status == AlertStatus.IN_PROGRESS:
            if new_status not in [AlertStatus.ESCALATED, AlertStatus.RESOLVED]:
                raise ValueError(
                    f"Invalid transition from {old_status.value} to {new_status.value}"
                )

        elif old_status == AlertStatus.ESCALATED:
            if new_status != AlertStatus.RESOLVED:
                raise ValueError(
                    f"Invalid transition from {old_status.value} to {new_status.value}"
                )

    @classmethod
    async def transition_alert(
        cls,
        db: AsyncSession,
        alert_id: uuid.UUID,
        new_status: AlertStatus,
        actor_id: Optional[uuid.UUID] = None,
    ) -> AlertRecord:
        """Execute a state machine status transition for an alert."""
        alert = cls.get_alert(alert_id)
        if not alert:
            raise ValueError(f"Alert with ID {alert_id} not found.")

        if isinstance(new_status, str):
            new_status = AlertStatus(new_status)

        cls.validate_transition(alert.status, new_status)

        old_status = alert.status
        alert.status = new_status
        alert.updated_at = datetime.now(timezone.utc)

        # Log to alert history
        alert.history.append(
            {
                "type": "STATUS_CHANGE",
                "old_value": old_status.value,
                "new_value": new_status.value,
                "timestamp": alert.updated_at.isoformat(),
                "actor_id": str(actor_id) if actor_id else None,
            }
        )

        # Emit workflow event
        await WorkflowEventService.emit_event(
            db=db,
            event_type=f"alert.{new_status.lower()}",
            payload={
                "alert_id": str(alert_id),
                "old_status": old_status.value,
                "new_status": new_status.value,
            },
        )

        # Log audit entry
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="alert.status_change",
            target_type="alert",
            target_id=alert_id,
            metadata={
                "old_status": old_status.value,
                "new_status": new_status.value,
            },
        )

        from src.services.alert_snapshot_service import AlertSnapshotService

        AlertSnapshotService.invalidate_cache()

        return alert

    @classmethod
    async def assign_alert(
        cls,
        db: AsyncSession,
        alert_id: uuid.UUID,
        owner_id: Optional[uuid.UUID],
        actor_id: Optional[uuid.UUID] = None,
    ) -> AlertRecord:
        """Assign alert to a specific analyst/owner."""
        alert = cls.get_alert(alert_id)
        if not alert:
            raise ValueError(f"Alert with ID {alert_id} not found.")

        old_owner = alert.owner
        alert.owner = owner_id
        alert.updated_at = datetime.now(timezone.utc)

        alert.history.append(
            {
                "type": "OWNER_CHANGE",
                "old_value": str(old_owner) if old_owner else None,
                "new_value": str(owner_id) if owner_id else None,
                "timestamp": alert.updated_at.isoformat(),
                "actor_id": str(actor_id) if actor_id else None,
            }
        )

        # Emit workflow event
        await WorkflowEventService.emit_event(
            db=db,
            event_type="alert.assigned",
            payload={
                "alert_id": str(alert_id),
                "old_owner": str(old_owner) if old_owner else None,
                "new_owner": str(owner_id) if owner_id else None,
            },
        )

        # Log audit entry
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="alert.assigned",
            target_type="alert",
            target_id=alert_id,
            metadata={
                "old_owner": str(old_owner) if old_owner else None,
                "new_owner": str(owner_id) if owner_id else None,
            },
        )

        from src.services.alert_snapshot_service import AlertSnapshotService

        AlertSnapshotService.invalidate_cache()

        return alert
