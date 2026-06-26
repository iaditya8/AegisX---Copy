import uuid
from typing import Any, Dict, List, Optional


class IncidentEvidenceService:
    # in-memory store: incident_id -> dict of evidence category -> list of copy of entities
    _evidence: Dict[uuid.UUID, Dict[str, List[Any]]] = {}

    @classmethod
    def clear_evidence(cls) -> None:
        """Clear the in-memory evidence store."""
        cls._evidence.clear()

    @classmethod
    def get_evidence(cls, incident_id: uuid.UUID) -> Dict[str, List[Any]]:
        """Get the read-only evidence references for an incident."""
        return cls._evidence.get(
            incident_id,
            {
                "alerts": [],
                "assets": [],
                "findings": [],
                "recommendations": [],
                "remediations": [],
            },
        )

    @classmethod
    def add_evidence(cls, incident_id: uuid.UUID, category: str, entity: Any) -> None:
        """Add a read-only historical reference of an entity to the incident evidence."""
        if incident_id not in cls._evidence:
            cls._evidence[incident_id] = {
                "alerts": [],
                "assets": [],
                "findings": [],
                "recommendations": [],
                "remediations": [],
            }

        if category not in cls._evidence[incident_id]:
            cls._evidence[incident_id][category] = []

        # Make a copy of the model or dict to preserve original state
        entity_copy = entity
        if hasattr(entity, "model_copy"):
            entity_copy = entity.model_copy()
        elif hasattr(entity, "copy"):
            entity_copy = entity.copy()

        # Check for duplicate by ID before appending
        entity_id = cls._get_entity_id(entity)
        if entity_id:
            exists = False
            for existing in cls._evidence[incident_id][category]:
                if cls._get_entity_id(existing) == entity_id:
                    exists = True
                    break
            if not exists:
                cls._evidence[incident_id][category].append(entity_copy)
        else:
            cls._evidence[incident_id][category].append(entity_copy)

    @classmethod
    def _get_entity_id(cls, entity: Any) -> Optional[uuid.UUID]:
        for attr in [
            "alert_id",
            "asset_id",
            "finding_id",
            "recommendation_id",
            "remediation_id",
            "id",
        ]:
            if hasattr(entity, attr):
                val = getattr(entity, attr)
                if isinstance(val, uuid.UUID):
                    return val
            if isinstance(entity, dict) and attr in entity:
                val = entity[attr]
                if isinstance(val, uuid.UUID):
                    return val
                try:
                    return uuid.UUID(str(val))
                except ValueError:
                    pass
        return None
