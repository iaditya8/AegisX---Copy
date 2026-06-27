import uuid
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.cyber_resilience import ResilienceStatus, ServiceCriticality
from src.services.cyber_resilience_service import CyberResilienceService
from src.services.recovery_objective_service import RecoveryObjectiveService
from src.services.service_resilience_service import ServiceResilienceService


class CyberResilienceSnapshotService:
    # Cache store: scope_id -> Snapshot dictionary
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear the snapshot cache."""
        cls._snapshots.clear()

    @classmethod
    def get_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Retrieve the cached snapshot, defaulting to a minimal fallback if missing or corrupted."""
        snap = cls._snapshots.get(scope_id)
        if not snap or not isinstance(snap, dict) or "summary" not in snap:
            return {
                "summary": {
                    "total_resilience_records": 0,
                    "active_resilience_records": 0,
                    "completed_resilience_records": 0,
                    "resilience_score": 100.0,
                    "readiness_score": 100.0,
                    "recovery_confidence_score": 100.0,
                    "critical_service_resilience": 100.0,
                    "objective_compliance": 100.0,
                },
                "records": {},
            }
        return snap

    @classmethod
    async def generate_snapshot(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None
    ) -> dict:
        """Dynamically rebuild snapshot stats from active resilience records."""
        all_recs = CyberResilienceService.get_all_resilience()
        if scope_id:
            all_recs = [r for r in all_recs if r.scope_id == scope_id]

        total_recs = len(all_recs)
        active_count = sum(1 for r in all_recs if r.status == ResilienceStatus.ACTIVE)
        comp_count = sum(
            1 for r in all_recs if r.status in (ResilienceStatus.COMPLETED, ResilienceStatus.CLOSED)
        )

        res_sum = sum(r.resilience_score for r in all_recs)
        read_sum = sum(r.readiness_score for r in all_recs)
        conf_sum = sum(r.recovery_confidence_score for r in all_recs)

        res_score = round(res_sum / total_recs, 2) if total_recs > 0 else 100.0
        read_score = round(read_sum / total_recs, 2) if total_recs > 0 else 100.0
        conf_score = round(conf_sum / total_recs, 2) if total_recs > 0 else 100.0

        # Critical service resilience average score
        crit_recs = [
            r
            for r in all_recs
            if r.service_criticality in (ServiceCriticality.HIGH, ServiceCriticality.MISSION_CRITICAL)
        ]
        crit_score = (
            round(sum(c.resilience_score for c in crit_recs) / len(crit_recs), 2)
            if crit_recs
            else 100.0
        )

        # Average objective compliance
        compliance_sum = sum(
            RecoveryObjectiveService.get_resilience_objective_compliance(r.resilience_id)
            for r in all_recs
        )
        obj_compliance = round(compliance_sum / total_recs, 2) if total_recs > 0 else 100.0

        records_track = {}
        for r in all_recs:
            records_track[str(r.resilience_id)] = {
                "resilience_id": str(r.resilience_id),
                "title": r.title,
                "status": r.status.value,
                "resilience_score": r.resilience_score,
                "readiness_score": r.readiness_score,
                "recovery_confidence_score": r.recovery_confidence_score,
            }

        snapshot = {
            "summary": {
                "total_resilience_records": total_recs,
                "active_resilience_records": active_count,
                "completed_resilience_records": comp_count,
                "resilience_score": res_score,
                "readiness_score": read_score,
                "recovery_confidence_score": conf_score,
                "critical_service_resilience": crit_score,
                "objective_compliance": obj_compliance,
            },
            "records": records_track,
        }

        cls._snapshots[scope_id] = snapshot
        return snapshot
