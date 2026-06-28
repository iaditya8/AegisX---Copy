from src.domain.entities.autonomous_planning import MilestoneType


class MilestoneTypeRegistry:
    @classmethod
    def validate(cls, milestone_type: str) -> bool:
        """Validate if milestone_type is a valid MilestoneType."""
        try:
            MilestoneType(milestone_type)
            return True
        except ValueError:
            return False
