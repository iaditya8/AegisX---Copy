from typing import Dict, Any


class KPIRegistry:
    # Key -> Default Target value
    PRE_SEEDED_KPIS = {
        "Mean Time To Detect": {
            "description": "Average duration from initial compromise to alert detection.",
            "target": 30.0,  # e.g., 30 minutes
        },
        "Mean Time To Respond": {
            "description": "Average duration from alert detection to containment/mitigation.",
            "target": 60.0,  # e.g., 60 minutes
        },
        "Critical Exposure Count": {
            "description": "Count of open exposures with critical severity.",
            "target": 0.0,
        },
        "Control Effectiveness Score": {
            "description": "Average security control effectiveness score.",
            "target": 80.0,
        },
        "Detection Coverage Score": {
            "description": "Overall coverage of ATT&CK techniques by active detections.",
            "target": 75.0,
        },
        "Threat Hunt Coverage": {
            "description": "Percentage of planned threat hunting hypotheses executed.",
            "target": 90.0,
        },
    }

    @classmethod
    def get_registered_kpis(cls) -> Dict[str, Dict[str, Any]]:
        """Retrieve pre-seeded KPIs definitions and targets."""
        return cls.PRE_SEEDED_KPIS

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a KPI name is pre-seeded/registered."""
        return name in cls.PRE_SEEDED_KPIS
