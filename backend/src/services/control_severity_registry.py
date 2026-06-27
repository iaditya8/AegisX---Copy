from typing import Union, Sequence
from src.domain.entities.control_validation import ControlSeverity


class ControlSeverityRegistry:
    @classmethod
    def resolve_severity(cls, severity: Union[ControlSeverity, str]) -> ControlSeverity:
        """Safely resolve control severity from enum or string, defaulting to LOW."""
        if isinstance(severity, ControlSeverity):
            return severity
        try:
            if hasattr(severity, "value"):
                val = str(severity.value).upper()
            else:
                val = str(severity).upper()
            return ControlSeverity(val)
        except ValueError:
            return ControlSeverity.LOW

    @classmethod
    def get_highest_severity(
        cls, severities: Sequence[Union[ControlSeverity, str]]
    ) -> ControlSeverity:
        """Determine the highest severity from a sequence of severities."""
        hierarchy = {
            ControlSeverity.CRITICAL: 4,
            ControlSeverity.HIGH: 3,
            ControlSeverity.MEDIUM: 2,
            ControlSeverity.LOW: 1,
        }
        max_val = 0
        max_sev = ControlSeverity.LOW
        for s in severities:
            resolved = cls.resolve_severity(s)
            val = hierarchy.get(resolved, 1)
            if val > max_val:
                max_val = val
                max_sev = resolved
        return max_sev
