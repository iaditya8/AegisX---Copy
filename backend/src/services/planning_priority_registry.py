from src.domain.entities.autonomous_planning import MilestoneType


class PlanningPriorityRegistry:
    # weight coefficients for scheduling/priority calculations
    _weights = {
        MilestoneType.REMEDIATION: 1.2,
        MilestoneType.VALIDATION: 0.8,
        MilestoneType.DEPLOYMENT: 1.0,
        MilestoneType.AUDIT: 0.5,
    }

    @classmethod
    def get_weight(cls, milestone_type: MilestoneType) -> float:
        """Get the weight coefficient for a milestone type."""
        norm_type = MilestoneType(milestone_type) if isinstance(milestone_type, str) else milestone_type
        return cls._weights.get(norm_type, 1.0)
