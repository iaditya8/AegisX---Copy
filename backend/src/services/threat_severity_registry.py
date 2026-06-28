from typing import List
from src.domain.entities.threat_intel import ThreatSeverity


class ThreatSeverityRegistry:
    SEVERITIES = {
        "LOW": 0.25,
        "MEDIUM": 0.50,
        "HIGH": 0.75,
        "CRITICAL": 1.00,
    }

    @classmethod
    def get_threshold(cls, label: str) -> float:
        """Resolve deterministic severity score threshold weight."""
        return cls.SEVERITIES.get(str(label).strip().upper(), 0.5)

    @classmethod
    def list_severities(cls) -> List[str]:
        """List all supported severity labels."""
        return list(cls.SEVERITIES.keys())

    @classmethod
    def validate(cls, label: str) -> bool:
        """Validate if a severity label is supported."""
        return str(label).strip().upper() in cls.SEVERITIES

    @classmethod
    def determine_severity(cls, score: float) -> ThreatSeverity:
        """Determine severity label based on threat score."""
        if score >= 90.0:
            return ThreatSeverity.LOW
        if score >= 75.0:
            return ThreatSeverity.MEDIUM
        if score >= 50.0:
            return ThreatSeverity.HIGH
        return ThreatSeverity.CRITICAL
