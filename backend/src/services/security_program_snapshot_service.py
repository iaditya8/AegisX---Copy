import uuid
from typing import Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.security_program import ProgramStatus, KPIStatus, KRIStatus
from src.services.security_program_service import SecurityProgramService
from src.services.kpi_service import KPIService
from src.services.kri_service import KRIService
from src.services.program_health_service import ProgramHealthService


class SecurityProgramSnapshotService:
    # Cache store: scope_id -> Snapshot dictionary
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}
    _score_trends: Dict[Optional[uuid.UUID], List[float]] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear the snapshot cache."""
        cls._snapshots.clear()
        cls._score_trends.clear()

    @classmethod
    def get_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Retrieve the cached snapshot, defaulting to a minimal fallback if missing or corrupted."""
        snap = cls._snapshots.get(scope_id)
        if not snap or not isinstance(snap, dict) or "summary" not in snap:
            return {
                "summary": {
                    "total_programs": 0,
                    "active_programs_count": 0,
                    "completed_programs_count": 0,
                    "average_program_score": 100.0,
                    "average_objective_completion": 100.0,
                    "average_initiative_completion": 100.0,
                    "kpi_performance_rate": 100.0,
                    "kri_exposure_rate": 100.0,
                    "trends": cls._score_trends.setdefault(scope_id, [100.0]),
                },
                "programs": {},
            }
        return snap

    @classmethod
    async def generate_snapshot(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None
    ) -> dict:
        """Dynamically rebuild snapshot stats from active program records."""
        all_programs = SecurityProgramService.get_all_programs()
        if scope_id:
            all_programs = [p for p in all_programs if p.scope_id == scope_id]

        total_programs = len(all_programs)
        
        # Calculate status counts
        active_count = sum(1 for p in all_programs if p.status in [ProgramStatus.ACTIVE, ProgramStatus.UNDER_REVIEW])
        completed_count = sum(1 for p in all_programs if p.status == ProgramStatus.COMPLETED)

        # Average stats
        if all_programs:
            avg_score = round(sum(p.program_score for p in all_programs) / len(all_programs), 2)
        else:
            avg_score = 100.0

        # Calculate metrics for each program and build mapping
        programs_track = {}
        total_objs = 0
        sum_obj_comp = 0.0
        total_inits = 0
        sum_init_comp = 0.0
        total_kpis = 0
        passed_kpis = 0
        total_kris = 0
        low_kris = 0

        for p in all_programs:
            resp = SecurityProgramService.to_response(p)
            
            # Aggregate stats
            total_objs += len(p.objectives)
            sum_obj_comp += sum(o.completion_percentage for o in p.objectives)
            total_inits += len(p.initiatives)
            sum_init_comp += sum(i.completion_percentage for i in p.initiatives)

            for k in resp.kpis:
                total_kpis += 1
                if k.status == KPIStatus.ON_TARGET:
                    passed_kpis += 1

            for kr in resp.kris:
                total_kris += 1
                if kr.status == KRIStatus.LOW_RISK:
                    low_kris += 1

            programs_track[str(p.program_id)] = {
                "program_id": str(p.program_id),
                "program_fingerprint": p.program_fingerprint,
                "name": p.name,
                "status": p.status.value,
                "program_score": p.program_score,
                "kpis": [k.model_dump() for k in resp.kpis],
                "kris": [kr.model_dump() for kr in resp.kris],
            }

        avg_obj = round(sum_obj_comp / total_objs, 2) if total_objs else 100.0
        avg_init = round(sum_init_comp / total_inits, 2) if total_inits else 100.0
        kpi_rate = round((passed_kpis / total_kpis) * 100.0, 2) if total_kpis else 100.0
        kri_rate = round((low_kris / total_kris) * 100.0, 2) if total_kris else 100.0

        # Update trend history
        trends = cls._score_trends.setdefault(scope_id, [])
        trends.append(avg_score)
        if len(trends) > 10:
            trends.pop(0)

        snapshot = {
            "summary": {
                "total_programs": total_programs,
                "active_programs_count": active_count,
                "completed_programs_count": completed_count,
                "average_program_score": avg_score,
                "average_objective_completion": avg_obj,
                "average_initiative_completion": avg_init,
                "kpi_performance_rate": kpi_rate,
                "kri_exposure_rate": kri_rate,
                "trends": list(trends),
            },
            "programs": programs_track,
        }

        cls._snapshots[scope_id] = snapshot
        return snapshot
