from src.domain.entities.alert import AlertSeverity, AlertType


class AlertSeverityRegistry:
    _registry = {
        AlertType.CRITICAL_FINDING: AlertSeverity.CRITICAL,
        AlertType.RISK_ACCEPTANCE_EXPIRATION: AlertSeverity.HIGH,
        AlertType.SLA_BREACH: AlertSeverity.HIGH,
        AlertType.COMPLIANCE_DRIFT: AlertSeverity.HIGH,
        AlertType.RISK_DRIFT: AlertSeverity.MEDIUM,
        AlertType.FINDING_DRIFT: AlertSeverity.MEDIUM,
        AlertType.ASSET_DRIFT: AlertSeverity.LOW,
    }

    @classmethod
    def get_severity(cls, alert_type: AlertType) -> AlertSeverity:
        """Map alert type to alert severity."""
        if isinstance(alert_type, str):
            try:
                alert_type = AlertType(alert_type)
            except ValueError:
                return AlertSeverity.LOW
        return cls._registry.get(alert_type, AlertSeverity.LOW)
