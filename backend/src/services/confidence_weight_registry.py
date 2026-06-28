class ConfidenceWeightRegistry:
    # default modifiers & decay factors per source type
    _weights = {
        "THREAT_INTEL": {"modifier": 1.1, "decay": 0.05},
        "RISK": {"modifier": 1.0, "decay": 0.08},
        "GRC": {"modifier": 0.9, "decay": 0.03},
        "POSTURE": {"modifier": 0.95, "decay": 0.04},
        "RESILIENCE": {"modifier": 1.0, "decay": 0.06},
        "KNOWLEDGE": {"modifier": 0.85, "decay": 0.02},
        "INCIDENT": {"modifier": 1.2, "decay": 0.1},
        "CASE": {"modifier": 1.15, "decay": 0.09},
        "ASSET": {"modifier": 1.0, "decay": 0.05},
    }

    @classmethod
    def get_parameters(cls, source_type: str) -> dict:
        """Get pre-seeded confidence weights and decay parameters."""
        norm = str(source_type).strip().upper()
        return cls._weights.get(norm, {"modifier": 1.0, "decay": 0.05})
