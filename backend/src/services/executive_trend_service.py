import uuid
from typing import Dict, List, Optional
from src.services.executive_scorecard_service import ExecutiveScorecardService


class ExecutiveTrendService:
    # Cache store: scope_id -> trend mapping
    _trends: Dict[Optional[uuid.UUID], Dict[str, List[float]]] = {}

    @classmethod
    def clear_trends(cls) -> None:
        """Clear the trend cache."""
        cls._trends.clear()

    @classmethod
    def get_trends(cls, scope_id: Optional[uuid.UUID] = None) -> Dict[str, List[float]]:
        """Retrieve cached trends for a scope."""
        t = cls._trends.get(scope_id)
        if not t:
            # Default fallback baselines
            t = {
                "overall_health_trend": [90.0, 92.0, 91.5],
                "risk_trend": [95.0, 94.0, 95.0],
                "program_trend": [80.0, 82.0, 83.0],
                "coverage_trend": [85.0, 87.0, 88.0],
            }
            cls._trends[scope_id] = t
        return t

    @classmethod
    def calculate_trends(cls, scope_id: Optional[uuid.UUID] = None) -> Dict[str, List[float]]:
        """Calculate and update historical trends over time."""
        current_trends = cls.get_trends(scope_id)
        scorecard = ExecutiveScorecardService.calculate_scorecard(scope_id)

        # Append new values
        current_trends["overall_health_trend"].append(scorecard.overall_health)
        current_trends["risk_trend"].append(scorecard.risk_score)
        current_trends["program_trend"].append(scorecard.program_score)
        current_trends["coverage_trend"].append(scorecard.coverage_score)

        # Cap trend size at 10 intervals
        for k in current_trends.keys():
            if len(current_trends[k]) > 10:
                current_trends[k].pop(0)

        cls._trends[scope_id] = current_trends
        return current_trends
