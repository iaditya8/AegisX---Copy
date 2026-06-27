from typing import Set
from src.domain.entities.cyber_risk_quantification import RiskScenarioType


class RiskScenarioRegistry:
    SCENARIOS = {s.value for s in RiskScenarioType}

    @classmethod
    def list_types(cls) -> Set[str]:
        """List all supported risk scenarios."""
        return cls.SCENARIOS

    @classmethod
    def validate(cls, scenario_type: str) -> bool:
        """Validate if a scenario type is supported."""
        return str(scenario_type).strip() in cls.SCENARIOS
