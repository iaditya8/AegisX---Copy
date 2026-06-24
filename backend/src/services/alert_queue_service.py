import uuid
from typing import Dict


class AlertQueueService:
    @classmethod
    def get_analyst_workload(cls, owner_id: uuid.UUID) -> int:
        """Count active alerts assigned to an analyst owner."""
        from src.domain.entities.alert import AlertStatus
        from src.services.alert_lifecycle_service import AlertLifecycleService

        alerts = AlertLifecycleService.get_all_alerts()
        active_statuses = [
            AlertStatus.OPEN,
            AlertStatus.ACKNOWLEDGED,
            AlertStatus.IN_PROGRESS,
            AlertStatus.ESCALATED,
        ]
        return sum(
            1 for a in alerts if a.owner == owner_id and a.status in active_statuses
        )

    @classmethod
    def get_queue_stats(cls) -> Dict[str, int]:
        """Return open/escalated/active alert statistics."""
        from src.domain.entities.alert import AlertStatus
        from src.services.alert_lifecycle_service import AlertLifecycleService

        alerts = AlertLifecycleService.get_all_alerts()
        open_count = sum(1 for a in alerts if a.status == AlertStatus.OPEN)
        escalated_count = sum(1 for a in alerts if a.status == AlertStatus.ESCALATED)
        in_progress_count = sum(
            1 for a in alerts if a.status == AlertStatus.IN_PROGRESS
        )
        acknowledged_count = sum(
            1 for a in alerts if a.status == AlertStatus.ACKNOWLEDGED
        )

        return {
            "open_alerts": open_count,
            "escalated_alerts": escalated_count,
            "in_progress_alerts": in_progress_count,
            "acknowledged_alerts": acknowledged_count,
            "total_active_alerts": open_count
            + escalated_count
            + in_progress_count
            + acknowledged_count,
        }
