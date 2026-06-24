from datetime import datetime, timezone
from typing import Any, List


class RemediationAgingService:
    @classmethod
    def get_age_days(cls, remediation: Any) -> float:
        """Calculate age in decimal days from creation."""
        now = datetime.now(timezone.utc)
        created_at = remediation.created_at
        if created_at.tzinfo is not None:
            now = now.astimezone(created_at.tzinfo)
        else:
            now = now.replace(tzinfo=None)
        return (now - created_at).total_seconds() / 86400.0

    @classmethod
    def is_breached(cls, remediation: Any) -> bool:
        """Determine if a remediation has breached its SLA."""
        now = datetime.now(timezone.utc)
        due_date = remediation.due_date
        if due_date.tzinfo is not None:
            now = now.astimezone(due_date.tzinfo)
        else:
            now = now.replace(tzinfo=None)
        return now > due_date

    @classmethod
    def get_overdue_items(cls) -> List[Any]:
        """Return all active remediations that have breached their SLA."""
        from src.services.remediation_service import RemediationService

        all_rems = RemediationService.get_all_remediations()
        overdue = []
        for r in all_rems:
            status = r.status.value
            if status not in ["REMEDIATED", "ACCEPTED_RISK", "FALSE_POSITIVE"]:
                if cls.is_breached(r):
                    overdue.append(r)
        return overdue

    @classmethod
    def get_sla_breaches(cls) -> List[Any]:
        """Return all remediations that have breached their SLA."""
        from src.services.remediation_service import RemediationService

        all_rems = RemediationService.get_all_remediations()
        breached = []
        for r in all_rems:
            if cls.is_breached(r):
                breached.append(r)
        return breached
