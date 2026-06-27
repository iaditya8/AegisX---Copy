class EffectivenessRegistry:
    @classmethod
    def get_effectiveness_level(cls, score: float) -> str:
        """Resolve a score to an effectiveness rating string."""
        if score >= 90.0:
            return "EXCELLENT"
        elif score >= 70.0:
            return "GOOD"
        elif score >= 50.0:
            return "FAIR"
        elif score >= 20.0:
            return "POOR"
        else:
            return "FAILED"
