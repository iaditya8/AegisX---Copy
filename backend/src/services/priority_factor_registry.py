from typing import Dict


class PriorityFactorRegistry:
    # Deterministic base weights summing up to 100
    WEIGHTS: Dict[str, float] = {
        "critical_finding": 30.0,
        "high_risk_asset": 25.0,
        "internet_exposed": 20.0,
        "rediscovered_finding": 15.0,
        "high_criticality": 10.0,
    }

    @classmethod
    def get_weight(cls, factor: str) -> float:
        """Get the base weight for a factor."""
        return cls.WEIGHTS.get(factor, 0.0)
