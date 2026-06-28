from src.domain.entities.security_decision import DecisionType


class DecisionTypeRegistry:
    @classmethod
    def validate(cls, decision_type: str) -> bool:
        """Validate if decision_type is a valid DecisionType."""
        try:
            DecisionType(decision_type)
            return True
        except ValueError:
            return False
