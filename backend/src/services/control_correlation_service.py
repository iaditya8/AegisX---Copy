import uuid
import copy
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.detection_service import DetectionService
from src.services.purple_team_service import PurpleTeamService
from src.services.hunt_service import HuntService
from src.services.exposure_service import ExposureService
from src.services.security_posture_service import SecurityPostureService


class ControlCorrelationService:
    # in-memory store: control_id -> list of correlations
    # Risk Correlation/Validation Preservation Rule: must never be deleted/modified.
    _correlations: Dict[uuid.UUID, List[dict]] = {}

    @classmethod
    def clear_correlations(cls) -> None:
        """Clear all control correlations."""
        cls._correlations.clear()

    @classmethod
    def get_correlations(cls, control_id: uuid.UUID) -> List[dict]:
        """Retrieve correlations for a control."""
        return copy.deepcopy(cls._correlations.get(control_id, []))

    @classmethod
    async def correlate_control(
        cls, db: AsyncSession, control_id: uuid.UUID, attack_techniques: List[str]
    ) -> List[dict]:
        """Correlate control against Detections, Purple Team exercises, Hunts, Exposures, and Postures."""
        tech_set = set(attack_techniques)

        # 1. Detections matching techniques
        detections = [
            d for d in DetectionService.get_all_detections() if d.technique_id in tech_set
        ]

        # 2. Purple Team Exercises matching techniques
        exercises = []
        for e in PurpleTeamService.get_all_exercises():
            if hasattr(e, "related_techniques") and e.related_techniques:
                if tech_set.intersection(e.related_techniques):
                    exercises.append(e)

        # 3. Hunts matching techniques
        hunts = []
        for h in HuntService.get_all_hunts():
            for entity in h.related_entities:
                if "technique" in entity.get("entity_type", "").lower():
                    if entity.get("entity_id") in tech_set:
                        hunts.append(h)
                        break

        # 4. Exposures
        exposures = [
            exp
            for exp in ExposureService.get_all_exposures()
            if any(t in str(exp.target) for t in tech_set)
        ]

        # 5. Postures
        postures = [
            p
            for p in SecurityPostureService.get_all_postures()
            if any(t in p.title or t in p.description for t in tech_set)
        ]

        # Build signatures to guarantee append-only uniqueness
        current = cls._correlations.setdefault(control_id, [])
        existing_signatures = {f"{c['entity_type']}:{c['entity_id']}" for c in current}

        new_correlations = []

        for d in detections:
            sig = f"Detection:{str(d.detection_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Detection", "entity_id": str(d.detection_id), "details": d.name})

        for ex in exercises:
            sig = f"PurpleTeamExercise:{str(ex.exercise_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "PurpleTeamExercise", "entity_id": str(ex.exercise_id), "details": ex.name})

        for h in hunts:
            sig = f"Hunt:{str(h.hunt_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Hunt", "entity_id": str(h.hunt_id), "details": h.title})

        for e in exposures:
            sig = f"Exposure:{str(e.exposure_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Exposure", "entity_id": str(e.exposure_id), "details": e.title})

        for p in postures:
            sig = f"SecurityPosture:{str(p.posture_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "SecurityPosture", "entity_id": str(p.posture_id), "details": p.title})

        # Append new correlations
        current.extend(new_correlations)
        return current
