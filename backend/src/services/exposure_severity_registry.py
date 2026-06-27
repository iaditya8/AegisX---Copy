from typing import Any, Union, Sequence
from src.domain.entities.exposure import ExposureSeverity


class ExposureSeverityRegistry:
    @classmethod
    def resolve_severity(cls, severity: Union[ExposureSeverity, str]) -> ExposureSeverity:
        """Safely resolve exposure severity from enum or string, defaulting to LOW."""
        if isinstance(severity, ExposureSeverity):
            return severity
        try:
            if hasattr(severity, "value"):
                val = str(severity.value).upper()
            else:
                val = str(severity).upper()
            return ExposureSeverity(val)
        except ValueError:
            return ExposureSeverity.LOW

    @classmethod
    def get_highest_severity(
        cls, severities: Sequence[Union[ExposureSeverity, str]]
    ) -> ExposureSeverity:
        """Determine the highest severity from a sequence of severities based on hierarchy."""
        hierarchy = {
            ExposureSeverity.CRITICAL: 4,
            ExposureSeverity.HIGH: 3,
            ExposureSeverity.MEDIUM: 2,
            ExposureSeverity.LOW: 1,
        }
        max_val = 0
        max_sev = ExposureSeverity.LOW
        for s in severities:
            resolved = cls.resolve_severity(s)
            val = hierarchy.get(resolved, 1)
            if val > max_val:
                max_val = val
                max_sev = resolved
        return max_sev
