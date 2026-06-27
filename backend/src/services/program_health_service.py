from typing import List, Dict
from src.domain.entities.security_program import (
    ProgramObjectiveResponse,
    ProgramInitiativeResponse,
    KPIResponse,
    KRIResponse,
    KPIStatus,
    KRIStatus,
)


class ProgramHealthService:
    @classmethod
    def calculate_health(
        cls,
        objectives: List[ProgramObjectiveResponse],
        initiatives: List[ProgramInitiativeResponse],
        kpis: List[KPIResponse],
        kris: List[KRIResponse],
    ) -> Dict[str, float]:
        """Deterministically calculate program metrics and health score."""
        # 1. Objective completion
        if not objectives:
            obj_comp = 100.0
        else:
            obj_comp = round(sum(o.completion_percentage for o in objectives) / len(objectives), 2)

        # 2. Initiative completion
        if not initiatives:
            init_comp = 100.0
        else:
            init_comp = round(sum(i.completion_percentage for i in initiatives) / len(initiatives), 2)

        # 3. KPI performance
        if not kpis:
            kpi_score = 100.0
        else:
            points = 0.0
            for k in kpis:
                if k.status == KPIStatus.ON_TARGET:
                    points += 100.0
                elif k.status == KPIStatus.AT_RISK:
                    points += 50.0
                else:
                    points += 0.0
            kpi_score = round(points / len(kpis), 2)

        # 4. KRI exposure
        if not kris:
            kri_score = 100.0
        else:
            points = 0.0
            for k in kris:
                if k.status == KRIStatus.LOW_RISK:
                    points += 100.0
                elif k.status == KRIStatus.MEDIUM_RISK:
                    points += 70.0
                elif k.status == KRIStatus.HIGH_RISK:
                    points += 30.0
                else:
                    points += 0.0
            kri_score = round(points / len(kris), 2)

        # Blended program score
        prog_score = round(obj_comp * 0.3 + init_comp * 0.3 + kpi_score * 0.2 + kri_score * 0.2, 2)

        return {
            "objective_completion": obj_comp,
            "initiative_completion": init_comp,
            "kpi_performance": kpi_score,
            "kri_exposure": kri_score,
            "program_score": prog_score,
        }
