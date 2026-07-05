import uuid
from typing import List, Dict, Any, Optional

from src.domain.entities.cyber_resilience import ServiceCriticality, ResilienceStatus
from src.services.cyber_resilience_service import CyberResilienceService


class ServiceResilienceService:
    @classmethod
    async def get_resilience_by_scope(cls, scope_id: Optional[uuid.UUID] = None) -> List[Any]:
        """Get all resilience records filtered by scope."""
        records = await CyberResilienceService.get_all_resilience()
        if scope_id:
            records = [r for r in records if r.scope_id == scope_id]
        return records

    @classmethod
    async def get_critical_services(cls, scope_id: Optional[uuid.UUID] = None) -> List[Any]:
        """Filter resilience records to MISSION_CRITICAL or HIGH criticality only."""
        records = await cls.get_resilience_by_scope(scope_id)
        return [
            r
            for r in records
            if r.service_criticality in (ServiceCriticality.HIGH, ServiceCriticality.MISSION_CRITICAL)
        ]

    @classmethod
    async def get_resilience_distribution(cls, scope_id: Optional[uuid.UUID] = None) -> Dict[str, int]:
        """Get status distribution breakdown counts."""
        records = await cls.get_resilience_by_scope(scope_id)
        dist = {s.value: 0 for s in ResilienceStatus}
        for r in records:
            val = r.status.value if hasattr(r.status, "value") else r.status
            dist[val] = dist.get(val, 0) + 1
        return dist

    @classmethod
    async def get_service_resilience_metrics(cls, scope_id: Optional[uuid.UUID] = None) -> List[Dict[str, Any]]:
        """Compute resilience score metrics aggregated per service."""
        records = await cls.get_resilience_by_scope(scope_id)
        services = {}
        for r in records:
            srv = r.service_name
            if srv not in services:
                services[srv] = {
                    "service_name": srv,
                    "criticality": r.service_criticality.value if hasattr(r.service_criticality, "value") else r.service_criticality,
                    "resilience_scores": [],
                    "readiness_scores": [],
                    "confidence_scores": [],
                }
            services[srv]["resilience_scores"].append(r.resilience_score)
            services[srv]["readiness_scores"].append(r.readiness_score)
            services[srv]["confidence_scores"].append(r.recovery_confidence_score)

        results = []
        for srv, val in services.items():
            res_avg = sum(val["resilience_scores"]) / len(val["resilience_scores"]) if val["resilience_scores"] else 0.0
            read_avg = sum(val["readiness_scores"]) / len(val["readiness_scores"]) if val["readiness_scores"] else 0.0
            conf_avg = sum(val["confidence_scores"]) / len(val["confidence_scores"]) if val["confidence_scores"] else 0.0

            results.append({
                "service_name": srv,
                "criticality": val["criticality"],
                "average_resilience_score": round(res_avg, 2),
                "average_readiness_score": round(read_avg, 2),
                "average_recovery_confidence_score": round(conf_avg, 2),
            })
        return results
