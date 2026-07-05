import uuid
from typing import Any, Dict, List, Optional
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import IncidentEvidence
from src.core.tenant import get_current_tenant_id


class IncidentEvidenceService:
    # in-memory store: incident_id -> dict of evidence category -> list of copies of entities
    _evidence: Dict[uuid.UUID, Dict[str, List[Any]]] = {}

    @classmethod
    def clear_evidence(cls) -> None:
        """Clear the in-memory evidence store."""
        cls._evidence.clear()

    @classmethod
    def _add_to_cache(cls, incident_id: uuid.UUID, category: str, entity: Any) -> None:
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
    async def get_evidence(cls, incident_id: uuid.UUID) -> Dict[str, List[Any]]:
        """Get the read-only evidence references for an incident."""
        # Query DB to ensure complete rehydration
        import json
        async with UnitOfWork() as uow:
            db_evidences = await uow.incident_repo.list_evidence(incident_id)
            res = {
                "alerts": [],
                "assets": [],
                "findings": [],
                "recommendations": [],
                "remediations": [],
            }
            for e in db_evidences:
                cat = e.category
                if cat not in res:
                    res[cat] = []
                try:
                    loaded = json.loads(e.details)
                except Exception:
                    loaded = e.details
                res[cat].append(loaded)
            return res

    @classmethod
    async def add_evidence(
        cls,
        incident_id: uuid.UUID,
        category: str,
        entity: Any,
        uow: Optional[UnitOfWork] = None,
    ) -> None:
        """Add a read-only historical reference of an entity to the incident evidence."""
        # Check duplicate
        entity_id = cls._get_entity_id(entity)
        if entity_id and incident_id in cls._evidence and category in cls._evidence[incident_id]:
            for existing in cls._evidence[incident_id][category]:
                if cls._get_entity_id(existing) == entity_id:
                    return

        # Warm cache first
        cls._add_to_cache(incident_id, category, entity)

        # Write to DB
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        
        # Details serialization helper
        details_dict = {}
        entity_id = cls._get_entity_id(entity) or uuid.uuid4()
        
        from datetime import datetime
        if hasattr(entity, "__dict__"):
            details_dict = {
                k: v.isoformat() if isinstance(v, datetime) else (str(v) if isinstance(v, uuid.UUID) else v)
                for k, v in entity.__dict__.items()
                if not k.startswith("_")
            }
        elif isinstance(entity, dict):
            details_dict = {
                k: v.isoformat() if isinstance(v, datetime) else (str(v) if isinstance(v, uuid.UUID) else v)
                for k, v in entity.items()
            }
        else:
            details_dict = {"value": str(entity)}

        async def _save(uow_inst: UnitOfWork):
            import json
            db_evidence = IncidentEvidence(
                tenant_id=tenant_id,
                incident_id=incident_id,
                category=category,
                entity_type=category,
                entity_id=entity_id,
                details=json.dumps(details_dict),
            )
            await uow_inst.incident_repo.save_evidence(db_evidence)

        if uow:
            await _save(uow)
        else:
            async with UnitOfWork() as new_uow:
                await _save(new_uow)
                await new_uow.commit()

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
