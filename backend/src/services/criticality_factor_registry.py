from typing import Dict

# Centralized registry of asset criticality scoring weights and limits.
CRITICALITY_FACTORS: Dict[str, int] = {
    "external_asset": 30,
    "internal_asset": 10,
    "critical_finding": 25,
    "high_finding": 15,
    "medium_finding": 10,
    "service_weight": 5,
    "technology_weight": 4,
    "service_cap": 25,
    "technology_cap": 20,
}
