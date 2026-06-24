from datetime import datetime, timezone
from typing import Any, List

from sqlalchemy.ext.asyncio import AsyncSession


class AlertEscalationService:
    @classmethod
    def get_alert_age_days(cls, alert: Any) -> float:
        """Calculate age in decimal days from creation."""
        now = datetime.now(timezone.utc)
        created_at = alert.created_at
        if created_at.tzinfo is not None:
            now = now.astimezone(created_at.tzinfo)
        else:
            now = now.replace(tzinfo=None)
        return (now - created_at).total_seconds() / 86400.0

    @classmethod
    async def process_escalations(cls, db: AsyncSession) -> List[Any]:
        """Scan active alerts, escalate those exceeding threshold age, and log events."""
        from src.domain.entities.alert import AlertStatus
        from src.services.alert_escalation_registry import (
            AlertEscalationRegistry,
        )
        from src.services.alert_lifecycle_service import AlertLifecycleService
        from src.services.audit_service import create_audit_entry
        from src.services.workflow_event_service import WorkflowEventService

        alerts = AlertLifecycleService.get_all_alerts()
        escalated_alerts = []

        for alert in alerts:
            # Only active, non-escalated, non-terminal alerts can escalate
            if alert.status in [
                AlertStatus.OPEN,
                AlertStatus.ACKNOWLEDGED,
                AlertStatus.IN_PROGRESS,
            ]:
                age_days = cls.get_alert_age_days(alert)
                threshold = AlertEscalationRegistry.get_threshold_days(alert.severity)
                if age_days >= threshold:
                    old_status = alert.status
                    alert.status = AlertStatus.ESCALATED
                    alert.updated_at = datetime.now(timezone.utc)

                    # Record escalation history
                    alert.escalation_history.append(
                        {
                            "from_status": old_status.value,
                            "timestamp": alert.updated_at.isoformat(),
                            "age_days": age_days,
                            "threshold_days": threshold,
                        }
                    )
                    alert.history.append(
                        {
                            "type": "STATUS_CHANGE",
                            "old_value": old_status.value,
                            "new_value": AlertStatus.ESCALATED.value,
                            "timestamp": alert.updated_at.isoformat(),
                            "actor_id": None,
                        }
                    )

                    # Emit workflow event
                    await WorkflowEventService.emit_event(
                        db=db,
                        event_type="alert.escalated",
                        payload={
                            "alert_id": str(alert.alert_id),
                            "old_status": old_status.value,
                            "new_status": AlertStatus.ESCALATED.value,
                            "age_days": age_days,
                            "threshold_days": threshold,
                        },
                    )

                    # Log audit entry
                    await create_audit_entry(
                        db=db,
                        actor_id=None,
                        action="alert.escalated",
                        target_type="alert",
                        target_id=alert.alert_id,
                        metadata={
                            "old_status": old_status.value,
                            "new_status": AlertStatus.ESCALATED.value,
                        },
                    )

                    escalated_alerts.append(alert)

        if escalated_alerts:
            from src.services.alert_snapshot_service import (
                AlertSnapshotService,
            )

            AlertSnapshotService.invalidate_cache()

        return escalated_alerts
