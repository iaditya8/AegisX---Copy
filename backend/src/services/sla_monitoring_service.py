from datetime import datetime, timedelta, timezone

from src.services.remediation_sla_registry import RemediationSLARegistry


class SLAMonitoringService:
    @classmethod
    def calculate_due_date(cls, created_at: datetime, priority: str) -> datetime:
        """Calculate target due date based on created_at and priority SLA days."""
        days = RemediationSLARegistry.get_sla_days(priority)
        return created_at + timedelta(days=days)

    @classmethod
    def calculate_days_remaining(cls, due_date: datetime) -> float:
        """Calculate decimal days remaining until due_date."""
        now = datetime.now(timezone.utc)
        if due_date.tzinfo is not None:
            now = now.astimezone(due_date.tzinfo)
        else:
            now = now.replace(tzinfo=None)

        diff = due_date - now
        return diff.total_seconds() / 86400.0

    @classmethod
    def get_sla_status(cls, due_date: datetime) -> str:
        """Return the SLA status: BREACHED, APPROACHING, or WITHIN_SLA."""
        days_rem = cls.calculate_days_remaining(due_date)
        if days_rem <= 0:
            return "BREACHED"
        elif days_rem <= 3.0:
            return "APPROACHING"
        else:
            return "WITHIN_SLA"
