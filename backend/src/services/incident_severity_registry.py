from typing import List

from src.domain.entities.alert import AlertSeverity
from src.domain.entities.incident import IncidentSeverity


class IncidentSeverityRegistry:
    @classmethod
    def calculate_severity(
        cls, alert_severities: List[AlertSeverity]
    ) -> IncidentSeverity:
        """Determine incident severity from a list of alert severities."""
        # Convert all string severities to AlertSeverity enum if needed
        severities = []
        for s in alert_severities:
            if isinstance(s, str):
                try:
                    severities.append(AlertSeverity(s))
                except ValueError:
                    pass
            elif isinstance(s, AlertSeverity):
                severities.append(s)

        if not severities:
            return IncidentSeverity.LOW

        # Rule 1: If any alert is CRITICAL -> incident is CRITICAL
        if any(s == AlertSeverity.CRITICAL for s in severities):
            return IncidentSeverity.CRITICAL

        high_count = sum(1 for s in severities if s == AlertSeverity.HIGH)
        medium_count = sum(1 for s in severities if s == AlertSeverity.MEDIUM)
        low_count = sum(1 for s in severities if s == AlertSeverity.LOW)

        # Rule 2: If multiple HIGH alerts -> HIGH
        if high_count >= 2:
            return IncidentSeverity.HIGH

        # Rule 3: If single HIGH alert -> HIGH (as a fallback)
        if high_count == 1:
            return IncidentSeverity.HIGH

        # Rule 4: If multiple MEDIUM alerts -> MEDIUM
        if medium_count >= 2:
            return IncidentSeverity.MEDIUM

        # Rule 5: If single MEDIUM alert -> MEDIUM
        if medium_count == 1:
            return IncidentSeverity.MEDIUM

        # Rule 6: Fallback for LOW alerts
        if low_count >= 3:
            return IncidentSeverity.MEDIUM

        return IncidentSeverity.LOW
