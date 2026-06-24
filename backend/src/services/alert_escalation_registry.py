from src.domain.entities.alert import AlertSeverity


class AlertEscalationRegistry:
    _registry = {
        AlertSeverity.CRITICAL: 1.0,  # 1 day
        AlertSeverity.HIGH: 3.0,  # 3 days
        AlertSeverity.MEDIUM: 7.0,  # 7 days
        AlertSeverity.LOW: 14.0,  # 14 days
    }

    @classmethod
    def get_threshold_days(cls, severity: AlertSeverity) -> float:
        """Get the aging threshold in days before an alert escalates."""
        if isinstance(severity, str):
            try:
                severity = AlertSeverity(severity)
            except ValueError:
                return 14.0
        return cls._registry.get(severity, 14.0)
