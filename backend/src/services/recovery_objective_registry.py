from typing import Dict, List


class RecoveryObjectiveRegistry:
    # Standard tiers represented in hours
    TIERS = {
        "RTO": [0.25, 1.0, 4.0, 24.0],
        "RPO": [0.0, 0.25, 1.0, 24.0],
    }

    @classmethod
    def get_tiers(cls, objective_type: str) -> List[float]:
        """Get standard hours tiers for RTO/RPO."""
        return cls.TIERS.get(objective_type, [])

    @classmethod
    def list_types(cls) -> List[str]:
        """List supported recovery objective types."""
        return list(cls.TIERS.keys())

    @classmethod
    def validate(cls, objective_type: str, value: float) -> bool:
        """Validate if a value is a standard tier for objective type."""
        return value in cls.TIERS.get(objective_type, [])
