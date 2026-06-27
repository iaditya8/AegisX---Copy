import hashlib
from typing import Sequence, Union
from src.domain.entities.purple_team import ExerciseType


class PurpleTeamFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls,
        exercise_type: ExerciseType,
        name: str,
        related_techniques: Sequence[str],
        related_entities: Sequence[Union[dict, str]],
    ) -> str:
        """Generate a stable deterministic SHA-256 fingerprint for a purple team exercise."""
        normalized_name = str(name).strip().lower()

        # Normalize and sort related techniques
        normalized_techniques = sorted([str(t).strip().upper() for t in related_techniques])
        techniques_str = ",".join(normalized_techniques)

        # Normalize and sort related entities
        normalized_entities = []
        for entity in related_entities:
            if isinstance(entity, dict):
                e_type = str(entity.get("entity_type", "")).strip().lower()
                e_id = str(entity.get("entity_id", "")).strip().lower()
                normalized_entities.append(f"{e_type}:{e_id}")
            else:
                normalized_entities.append(str(entity).strip().lower())

        normalized_entities.sort()
        entities_str = ",".join(normalized_entities)

        payload = (
            f"type:{exercise_type.value}|"
            f"name:{normalized_name}|"
            f"techniques:{techniques_str}|"
            f"entities:{entities_str}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
