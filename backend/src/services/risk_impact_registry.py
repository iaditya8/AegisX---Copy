from typing import Dict, List


class RiskImpactRegistry:
    IMPACTS = {
        "LOW": 0.1,
        "MEDIUM": 0.3,
        "HIGH": 0.6,
        "CRITICAL": 0.9,
    }

    @classmethod
    def get_factor(cls, label: str) -> float:
        """Resolve deterministic Exposure Factor for an impact label."""
        return cls.IMPACTS.get(str(label).strip().upper(), 0.5)

    @classmethod
    def list_impacts(cls) -> List[str]:
        """List all supported impact labels."""
        return list(cls.IMPACTS.keys())

    @classmethod
    def validate(cls, label: str) -> bool:
        """Validate if an impact label is supported."""
        return str(label).strip().upper() in cls.IMPACTS
