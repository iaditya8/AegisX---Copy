from typing import List, Union

from src.domain.entities.hunt import HuntSeverity


class HuntSeverityRegistry:
    @classmethod
    def resolve_severity(cls, severity: Union[HuntSeverity, str]) -> HuntSeverity:
        """Safely resolve hunt severity from enum or string, defaulting to LOW."""
        if isinstance(severity, HuntSeverity):
            return severity
        try:
            if hasattr(severity, "value"):
                val = str(severity.value).upper()
            else:
                val = str(severity).upper()
            return HuntSeverity(val)
        except ValueError:
            return HuntSeverity.LOW

    @classmethod
    def get_highest_severity(
        cls, severities: List[Union[HuntSeverity, str]]
    ) -> HuntSeverity:
        """Determine highest severity from a list of severities based on hierarchy."""
        hierarchy = {
            HuntSeverity.CRITICAL: 4,
            HuntSeverity.HIGH: 3,
            HuntSeverity.MEDIUM: 2,
            HuntSeverity.LOW: 1,
        }
        max_val = 0
        max_sev = HuntSeverity.LOW
        for s in severities:
            resolved = cls.resolve_severity(s)
            val = hierarchy.get(resolved, 1)
            if val > max_val:
                max_val = val
                max_sev = resolved
        return max_sev
