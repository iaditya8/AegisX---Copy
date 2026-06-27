import uuid
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.detection_service import DetectionService
from src.services.purple_team_service import PurpleTeamService
from src.services.hunt_service import HuntService
from src.services.exposure_service import ExposureService


class ControlCoverageService:
    @classmethod
    async def calculate_coverage(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None
    ) -> Dict[str, float]:
        """Calculate ATT&CK, Detection, Purple Team, Hunt, and Exposure coverage across scopes."""
        from src.services.control_validation_service import ControlValidationService

        controls = ControlValidationService.get_all_controls()
        if scope_id:
            controls = [c for c in controls if c.scope_id == scope_id]

        all_techs = set()
        for c in controls:
            all_techs.update(c.attack_techniques)

        passed_techs = set()
        for c in controls:
            validations = ControlValidationService.get_validations(c.control_id)
            for v in validations:
                status_str = str(v.validation_status.value).upper()
                if "PASS" in status_str:
                    passed_techs.add(v.attack_technique)

        # 1. ATT&CK Coverage
        att_ck_cov = round((len(passed_techs) / len(all_techs)) * 100.0, 2) if all_techs else 100.0

        # 2. Detection Coverage
        detections = DetectionService.get_all_detections()
        mapped_detections = [d for d in detections if d.technique_id in passed_techs]
        det_cov = round((len(mapped_detections) / len(detections)) * 100.0, 2) if detections else 100.0

        # 3. Purple Team Coverage
        exercises = PurpleTeamService.get_all_exercises()
        if scope_id:
            exercises = [e for e in exercises if e.scope_id == scope_id]
        pt_techs = set()
        for e in exercises:
            if hasattr(e, "related_techniques") and e.related_techniques:
                pt_techs.update(e.related_techniques)
        covered_pt = pt_techs.intersection(passed_techs)
        pt_cov = round((len(covered_pt) / len(pt_techs)) * 100.0, 2) if pt_techs else 100.0

        # 4. Hunt Coverage
        hunts = HuntService.get_all_hunts()
        if scope_id:
            hunts = [h for h in hunts if h.scope_id == scope_id]
        hunt_techs = set()
        for h in hunts:
            # Check if hunt has matched techniques or raw list
            techs = h.related_entities
            for t in techs:
                if "technique" in t.get("entity_type", "").lower():
                    hunt_techs.add(t.get("entity_id"))
        covered_hunts = hunt_techs.intersection(passed_techs)
        hunt_cov = round((len(covered_hunts) / len(hunt_techs)) * 100.0, 2) if hunt_techs else 100.0

        # 5. Exposure Coverage
        exposures = ExposureService.get_all_exposures()
        resolved_exps = [e for e in exposures if e.status.value in ["MITIGATED", "CLOSED"]]
        exp_cov = round((len(resolved_exps) / len(exposures)) * 100.0, 2) if exposures else 100.0

        return {
            "attack_coverage": att_ck_cov,
            "detection_coverage": det_cov,
            "purple_team_coverage": pt_cov,
            "hunt_coverage": hunt_cov,
            "exposure_coverage": exp_cov,
        }
