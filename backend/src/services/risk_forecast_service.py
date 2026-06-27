import uuid
from typing import List
from src.domain.entities.cyber_risk_quantification import RiskForecastResponse


class RiskForecastService:
    @classmethod
    def get_forecasts(
        cls, risk_id: uuid.UUID, ale: float, exposure_value: float
    ) -> List[RiskForecastResponse]:
        """Project 4-quarter deterministic risk forecasts."""
        quarters = ["Q1", "Q2", "Q3", "Q4"]
        forecasts = []
        for i, q in enumerate(quarters):
            decay = 1.0 - (i * 0.05)
            forecasts.append(
                RiskForecastResponse(
                    risk_id=risk_id,
                    quarter=q,
                    projected_loss=round(ale * decay, 2),
                    exposure_value=round(exposure_value * decay, 2),
                )
            )
        return forecasts

    @classmethod
    def calculate(cls) -> None:
        """Run forecasts generation logic (read-only derived intelligence)."""
        pass
