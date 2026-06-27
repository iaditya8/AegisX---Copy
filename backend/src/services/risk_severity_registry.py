from typing import Union, Sequence
from src.domain.entities.security_posture import PostureSeverity


class RiskSeverityRegistry:
    @classmethod
    def resolve_severity(cls, severity: Union[PostureSeverity, str]) -> PostureSeverity:
        """Safely resolve posture severity from enum or string, defaulting to LOW."""
        if isinstance(severity, PostureSeverity):
            return severity
        try:
            if hasattr(severity, "value"):
                val = str(severity.value).upper()
            else:
                val = str(severity).upper()
            return PostureSeverity(val)
        except ValueError:
            return PostureSeverity.LOW

    @classmethod
    def get_highest_severity(
        cls, severities: Sequence[Union[PostureSeverity, str]]
    ) -> PostureSeverity:
        """Determine the highest severity from a sequence of severities."""
        hierarchy = {
            PostureSeverity.CRITICAL: 4,
            PostureSeverity.HIGH: 3,
            PostureSeverity.MEDIUM: 2,
            PostureSeverity.LOW: 1,
        }
        max_val = 0
        max_sev = PostureSeverity.LOW
        for s in severities:
            resolved = cls.resolve_severity(s)
            val = hierarchy.get(resolved, 1)
            if val > max_val:
                max_val = val
                max_sev = resolved
        return max_sev
