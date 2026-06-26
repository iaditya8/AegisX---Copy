from typing import List, Union
from src.domain.entities.detection import DetectionSeverity


class DetectionSeverityRegistry:
    @classmethod
    def resolve_severity(cls, severity: Union[DetectionSeverity, str]) -> DetectionSeverity:
        """Safely resolve detection severity from enum or string, defaulting to LOW."""
        if isinstance(severity, DetectionSeverity):
            return severity
        try:
            return DetectionSeverity(str(severity).upper())
        except ValueError:
            return DetectionSeverity.LOW

    @classmethod
    def get_highest_severity(
        cls, severities: List[Union[DetectionSeverity, str]]
    ) -> DetectionSeverity:
        """Determine highest severity from a list of severities based on severity hierarchy."""
        hierarchy = {
            DetectionSeverity.CRITICAL: 4,
            DetectionSeverity.HIGH: 3,
            DetectionSeverity.MEDIUM: 2,
            DetectionSeverity.LOW: 1,
        }
        max_val = 0
        max_sev = DetectionSeverity.LOW
        for s in severities:
            resolved = cls.resolve_severity(s)
            val = hierarchy.get(resolved, 1)
            if val > max_val:
                max_val = val
                max_sev = resolved
        return max_sev
