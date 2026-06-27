from src.domain.entities.cyber_resilience import ServiceCriticality


class CriticalityRegistry:
    FACTORS = {
        ServiceCriticality.LOW: 1.0,
        ServiceCriticality.MEDIUM: 1.5,
        ServiceCriticality.HIGH: 2.0,
        ServiceCriticality.MISSION_CRITICAL: 3.0,
    }

    @classmethod
    def get_weight(cls, criticality: ServiceCriticality) -> float:
        """Resolve deterministic weight factors for service criticality."""
        return cls.FACTORS.get(criticality, 1.0)
