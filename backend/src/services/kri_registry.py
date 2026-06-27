from typing import Dict, Any


class KRIRegistry:
    # Key -> Default Threshold value
    PRE_SEEDED_KRIS = {
        "Critical Risk Growth": {
            "description": "Increase rate of critical risk issues over 30 days.",
            "threshold": 10.0,  # e.g., max 10% growth
        },
        "Open Incident Growth": {
            "description": "Growth in open unresolved incidents.",
            "threshold": 15.0,  # e.g., max 15%
        },
        "Exposure Growth": {
            "description": "Growth rate of newly discovered external exposures.",
            "threshold": 5.0,
        },
        "Detection Regression": {
            "description": "Count of previously active detections disabled or deprecated.",
            "threshold": 0.0,
        },
        "Threat Coverage Regression": {
            "description": "Decrease in ATT&CK technique coverage.",
            "threshold": 0.0,
        },
    }

    @classmethod
    def get_registered_kris(cls) -> Dict[str, Dict[str, Any]]:
        """Retrieve pre-seeded KRIs definitions and thresholds."""
        return cls.PRE_SEEDED_KRIS

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a KRI name is pre-seeded/registered."""
        return name in cls.PRE_SEEDED_KRIS
