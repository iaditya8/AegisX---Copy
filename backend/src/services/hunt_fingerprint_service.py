import hashlib
from typing import List, Union

from src.domain.entities.hunt import HuntType


class HuntFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls, hunt_type: HuntType, title: str, related_entities: List[Union[dict, str]]
    ) -> str:
        """Generate a stable deterministic SHA-256 fingerprint for a hunt."""
        normalized_title = str(title).strip().lower()

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

        payload = f"type:{hunt_type.value}|title:{normalized_title}|entities:{entities_str}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
