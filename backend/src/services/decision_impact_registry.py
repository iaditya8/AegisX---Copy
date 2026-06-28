from src.domain.entities.security_decision import DecisionImpact


class DecisionImpactRegistry:
    @classmethod
    def validate(cls, decision_impact: str) -> bool:
        """Validate if decision_impact is a valid DecisionImpact."""
        try:
            DecisionImpact(decision_impact)
            return True
        except ValueError:
            return False
