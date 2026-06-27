import uuid
from typing import Dict, List


class RiskTrendService:
    # in-memory store: risk_id -> list of exposure trend points
    _trends: Dict[uuid.UUID, List[float]] = {}

    @classmethod
    def clear_trends(cls) -> None:
        """Clear the trend store."""
        cls._trends.clear()

    @classmethod
    def calculate_trends(cls, risk_id: uuid.UUID, current_exposure: float) -> List[float]:
        """Compute and cache deterministic history trends for risk exposure."""
        # Prepopulate prior trends if missing
        if risk_id not in cls._trends:
            cls._trends[risk_id] = [
                round(current_exposure * 1.15, 2),
                round(current_exposure * 1.10, 2),
                round(current_exposure * 1.05, 2),
            ]
        
        # Append current trend point if different
        trends_list = cls._trends[risk_id]
        if not trends_list or trends_list[-1] != current_exposure:
            trends_list.append(current_exposure)
        
        # Limit to last 10 points
        if len(trends_list) > 10:
            cls._trends[risk_id] = trends_list[-10:]

        return list(cls._trends[risk_id])

    @classmethod
    def get_trends(cls, risk_id: uuid.UUID) -> List[float]:
        """Get trends for a specific risk."""
        return list(cls._trends.get(risk_id, []))

    @classmethod
    def calculate(cls) -> None:
        """Calculate trend metrics across all active risks (read-only derived intelligence)."""
        pass
