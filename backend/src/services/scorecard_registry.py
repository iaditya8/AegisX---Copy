from src.domain.entities.executive_reporting import ScorecardStatus


class ScorecardRegistry:
    @classmethod
    def resolve_status(cls, health_score: float) -> ScorecardStatus:
        """Resolve ScorecardStatus based on health score thresholds."""
        if health_score >= 85.0:
            return ScorecardStatus.HEALTHY
        elif health_score >= 70.0:
            return ScorecardStatus.WATCH
        elif health_score >= 50.0:
            return ScorecardStatus.AT_RISK
        else:
            return ScorecardStatus.CRITICAL
