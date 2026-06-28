class PropagationDirectionRegistry:
    _directions = {
        "RISK_TO_DECISION",
        "DECISION_TO_PLAN",
        "THREAT_TO_KNOWLEDGE",
        "POSTURE_TO_COMPLIANCE",
    }

    @classmethod
    def validate(cls, direction: str) -> bool:
        """Validate if propagation direction is supported by the fabric."""
        return str(direction).strip().upper() in cls._directions
