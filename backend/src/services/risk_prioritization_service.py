from typing import List, Any
from src.domain.entities.security_posture import PostureSeverity


class RiskPrioritizationService:
    @classmethod
    def prioritize_postures(cls, postures: List[Any]) -> List[Any]:
        """Sort and prioritize security posture records based on severity level and risk score descending."""
        severity_weights = {
            PostureSeverity.CRITICAL: 4,
            PostureSeverity.HIGH: 3,
            PostureSeverity.MEDIUM: 2,
            PostureSeverity.LOW: 1,
        }

        # Sort by severity weight descending, then risk score descending
        return sorted(
            postures,
            key=lambda p: (severity_weights.get(p.severity, 1), p.risk_score),
            reverse=True,
        )
