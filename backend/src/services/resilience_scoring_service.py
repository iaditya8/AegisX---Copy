import uuid
from typing import Dict, Optional
from src.domain.entities.cyber_resilience import ResilienceStatus, ServiceCriticality
from src.services.criticality_registry import CriticalityRegistry
from src.services.recovery_objective_service import RecoveryObjectiveService


class ResilienceScoringService:
    @classmethod
    def calculate_readiness_score(cls, resilience_id: uuid.UUID, status: ResilienceStatus) -> float:
        """Calculate readiness score weighted: plan coverage 40%, validation coverage 30%, testing status 30%."""
        if status in (ResilienceStatus.VALIDATED, ResilienceStatus.COMPLETED, ResilienceStatus.CLOSED):
            plan_cov = 100.0
            val_cov = 100.0
            test_status = 100.0
        elif status == ResilienceStatus.UNDER_REVIEW:
            plan_cov = 90.0
            val_cov = 80.0
            test_status = 85.0
        elif status == ResilienceStatus.ACTIVE:
            plan_cov = 80.0
            val_cov = 70.0
            test_status = 75.0
        else:
            plan_cov = 50.0
            val_cov = 40.0
            test_status = 45.0

        return round(plan_cov * 0.4 + val_cov * 0.3 + test_status * 0.3, 2)

    @classmethod
    def calculate_recovery_confidence_score(
        cls, resilience_id: uuid.UUID, status: ResilienceStatus, obj_compliance: float, readiness_score: float
    ) -> float:
        """Calculate recovery confidence score weighted: objective compliance 40%, validation depth 30%, readiness state 30%."""
        if status in (ResilienceStatus.VALIDATED, ResilienceStatus.COMPLETED, ResilienceStatus.CLOSED):
            val_depth = 100.0
        elif status == ResilienceStatus.UNDER_REVIEW:
            val_depth = 80.0
        elif status == ResilienceStatus.ACTIVE:
            val_depth = 70.0
        else:
            val_depth = 50.0

        return round(obj_compliance * 0.4 + val_depth * 0.3 + readiness_score * 0.3, 2)

    @classmethod
    def calculate_resilience_score(
        cls,
        resilience_id: uuid.UUID,
        status: ResilienceStatus,
        criticality: ServiceCriticality,
        readiness_score: float,
        obj_compliance: float,
    ) -> float:
        """Calculate resilience score weighted: readiness 30%, objective compliance 30%, criticality factor 20%, validation rate 20%."""
        # Criticality weight mapping to 0-100 scale
        crit_weight = CriticalityRegistry.get_weight(criticality)
        crit_factor = min(crit_weight / 3.0 * 100.0, 100.0)

        # Validation rate mapping
        if status in (ResilienceStatus.VALIDATED, ResilienceStatus.COMPLETED, ResilienceStatus.CLOSED):
            val_rate = 100.0
        elif status == ResilienceStatus.UNDER_REVIEW:
            val_rate = 80.0
        elif status == ResilienceStatus.ACTIVE:
            val_rate = 65.0
        else:
            val_rate = 40.0

        return round(readiness_score * 0.3 + obj_compliance * 0.3 + crit_factor * 0.2 + val_rate * 0.2, 2)
