from typing import List

from src.domain.entities.case import CaseSeverity
from src.domain.entities.incident import IncidentSeverity


class CaseSeverityRegistry:
    @classmethod
    def calculate_severity(
        cls, incident_severities: List[IncidentSeverity]
    ) -> CaseSeverity:
        """Determine case severity based on the maximum severity of contained incidents."""
        severities = []
        for s in incident_severities:
            if isinstance(s, str):
                try:
                    severities.append(IncidentSeverity(s))
                except ValueError:
                    pass
            elif isinstance(s, IncidentSeverity):
                severities.append(s)

        if not severities:
            return CaseSeverity.LOW

        if any(s == IncidentSeverity.CRITICAL for s in severities):
            return CaseSeverity.CRITICAL
        if any(s == IncidentSeverity.HIGH for s in severities):
            return CaseSeverity.HIGH
        if any(s == IncidentSeverity.MEDIUM for s in severities):
            return CaseSeverity.MEDIUM
        return CaseSeverity.LOW
