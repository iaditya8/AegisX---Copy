import uuid
from typing import Dict, Any, Optional

from src.services.incident_service import IncidentService
from src.services.exposure_service import ExposureService


class ExecutiveHeatmapService:
    @classmethod
    def generate_heatmap(cls, scope_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """Generate risk heatmap coordinates (Likelihood and Impact on 1-5 scale) for core categories."""
        # Dynamic calculations based on incidents and exposures count
        incident_count = len(IncidentService.get_all_incidents())
        exposure_count = len(ExposureService.get_all_exposures())

        inc_likelihood = min(max(1, incident_count // 3), 5)
        exp_likelihood = min(max(1, exposure_count // 5), 5)

        return {
            "categories": {
                "Vulnerability Risk": {
                    "likelihood": 2,
                    "impact": 4,
                    "description": "Vulnerability patching backlog risks.",
                },
                "Incident Risk": {
                    "likelihood": inc_likelihood,
                    "impact": 4,
                    "description": "Likelihood and impact of active breaches/malware.",
                },
                "Coverage Risk": {
                    "likelihood": 2,
                    "impact": 3,
                    "description": "Detection gaps or disabled rules.",
                },
                "Exposure Risk": {
                    "likelihood": exp_likelihood,
                    "impact": 3,
                    "description": "Asset exposure visibility on external attack surface.",
                },
            },
            "matrix_dimensions": {"max_likelihood": 5, "max_impact": 5},
        }
