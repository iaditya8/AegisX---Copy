from src.domain.entities.security_decision import DecisionType


class TradeoffFactorRegistry:
    # Pre-seeded: maps DecisionType to dict of cost-benefit parameters
    _factors = {
        DecisionType.REMEDIATION: {
            "cost_multiplier": 1.2,
            "risk_reduction_coefficient": 0.8,
        },
        DecisionType.MITIGATION: {
            "cost_multiplier": 0.8,
            "risk_reduction_coefficient": 0.6,
        },
        DecisionType.TRANSFER: {
            "cost_multiplier": 1.5,
            "risk_reduction_coefficient": 0.4,
        },
        DecisionType.ACCEPTANCE: {
            "cost_multiplier": 0.1,
            "risk_reduction_coefficient": 0.0,
        },
        DecisionType.COMPLIANCE_CONTROL: {
            "cost_multiplier": 1.0,
            "risk_reduction_coefficient": 0.7,
        },
    }

    @classmethod
    def get_factors(cls, decision_type: DecisionType) -> dict:
        """Retrieve pre-seeded factors for a decision type."""
        # Normalize in case type is string or enum
        norm_type = DecisionType(decision_type) if isinstance(decision_type, str) else decision_type
        return cls._factors.get(
            norm_type,
            {"cost_multiplier": 1.0, "risk_reduction_coefficient": 0.5},
        )
