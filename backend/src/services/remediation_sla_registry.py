from typing import Dict


class RemediationSLARegistry:
    # Maps priorities strictly to SLA days to avoid hardcoded values
    SLA_DAYS: Dict[str, int] = {
        "CRITICAL": 7,
        "HIGH": 30,
        "MEDIUM": 60,
        "LOW": 90,
    }

    @classmethod
    def get_sla_days(cls, priority: str) -> int:
        """Get the SLA deadline days for a given recommendation priority."""
        return cls.SLA_DAYS.get(priority.upper(), 30)
