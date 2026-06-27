import uuid
from typing import Dict, Optional

from src.domain.entities.purple_team import ExerciseType, ValidationStatus
from src.domain.entities.detection import DetectionStatus
from src.services.purple_team_service import PurpleTeamService
from src.services.detection_service import DetectionService
from src.services.attack_validation_registry import AttackValidationRegistry
from src.services.adversary_emulation_service import AdversaryEmulationService
from src.services.attack_validation_service import AttackValidationService


class PurpleTeamCoverageService:
    @classmethod
    def calculate_coverage(cls, scope_id: Optional[uuid.UUID] = None) -> Dict[str, float]:
        """Calculate Purple Team coverage percentages for attack, actors, campaigns, and validations."""
        # 1. Attack Coverage
        techniques = AttackValidationRegistry.get_registered_techniques()
        total_techs = len(techniques)

        detections = DetectionService.get_all_detections()
        active_detections = [
            d for d in detections
            if d.status == DetectionStatus.ACTIVE and (not scope_id or d.scope_id == scope_id)
        ]

        covered_techs = {
            t for t in techniques
            if any(t in d.attack_techniques for d in active_detections)
        }
        attack_coverage = (len(covered_techs) / total_techs * 100.0) if total_techs > 0 else 100.0

        # 2. Actor Coverage
        actors = ["APT29", "APT28", "Lazarus", "FIN7"]
        covered_actors = 0
        for actor in actors:
            actor_techs = AdversaryEmulationService.get_techniques_for_actor(actor)
            if actor_techs and any(t in covered_techs for t in actor_techs):
                covered_actors += 1
        actor_coverage = (covered_actors / len(actors) * 100.0) if actors else 100.0

        # 3. Campaign Coverage
        campaign_map = {
            "Operation Ghost": ["T1059", "T1078"],
            "Operation Grizzly": ["T1027", "T1105"],
        }
        covered_campaigns = 0
        for name, camp_techs in campaign_map.items():
            if any(t in covered_techs for t in camp_techs):
                covered_campaigns += 1
        campaign_coverage = (covered_campaigns / len(campaign_map) * 100.0) if campaign_map else 100.0

        # 4. Validation Coverage
        validations = AttackValidationService.get_all_validations()
        if scope_id:
            validations = [
                v for v in validations
                if PurpleTeamService.get_exercise(v.exercise_id)
                and PurpleTeamService.get_exercise(v.exercise_id).scope_id == scope_id
            ]

        # Filter by exercise type
        det_vals = [
            v for v in validations
            if PurpleTeamService.get_exercise(v.exercise_id).exercise_type == ExerciseType.DETECTION_VALIDATION
        ]
        ctrl_vals = [
            v for v in validations
            if PurpleTeamService.get_exercise(v.exercise_id).exercise_type == ExerciseType.CONTROL_VALIDATION
        ]

        det_passed = [v for v in det_vals if v.validation_status == ValidationStatus.PASSED]
        ctrl_passed = [v for v in ctrl_vals if v.validation_status == ValidationStatus.PASSED]

        det_coverage = (len(det_passed) / len(det_vals) * 100.0) if det_vals else 100.0
        ctrl_coverage = (len(ctrl_passed) / len(ctrl_vals) * 100.0) if ctrl_vals else 100.0

        return {
            "attack_coverage": round(attack_coverage, 2),
            "actor_coverage": round(actor_coverage, 2),
            "campaign_coverage": round(campaign_coverage, 2),
            "detection_validation_coverage": round(det_coverage, 2),
            "control_validation_coverage": round(ctrl_coverage, 2),
        }
