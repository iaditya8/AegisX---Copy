from typing import Dict, Any


class QueueAnalyticsService:
    # in-memory store for queue statistics
    _stats = {
        "queue_size": 24,
        "processing_efficiency": 94.5,
        "alert_backlog": 12,
        "incident_backlog": 2,
        "case_backlog": 1,
    }

    @classmethod
    def get_queue_summary(cls) -> Dict[str, Any]:
        """Retrieve queue sizes, efficiency and backlog summary metrics."""
        return {
            "queue_size": cls._stats["queue_size"],
            "processing_efficiency": cls._stats["processing_efficiency"],
            "backlog_metrics": {
                "alert_backlog": cls._stats["alert_backlog"],
                "incident_backlog": cls._stats["incident_backlog"],
                "case_backlog": cls._stats["case_backlog"],
            },
        }

    @classmethod
    def update_queue_metrics(
        cls, queue_size: int, efficiency: float, alert_b: int, incident_b: int, case_b: int
    ) -> None:
        """Update the queue metrics in-memory."""
        cls._stats["queue_size"] = queue_size
        cls._stats["processing_efficiency"] = efficiency
        cls._stats["alert_backlog"] = alert_b
        cls._stats["incident_backlog"] = incident_b
        cls._stats["case_backlog"] = case_b
