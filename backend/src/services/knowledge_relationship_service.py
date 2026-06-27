import uuid
from typing import Dict, List
from src.domain.entities.security_knowledge import KnowledgeRelationshipResponse


class KnowledgeRelationshipService:
    # in-memory relationship store: relationship_id -> KnowledgeRelationshipResponse
    _relationships: Dict[uuid.UUID, KnowledgeRelationshipResponse] = {}

    @classmethod
    def clear_relationships(cls) -> None:
        """Clear all mapped relationships."""
        cls._relationships.clear()

    @classmethod
    def add_relationship(
        cls,
        source_id: uuid.UUID,
        source_type: str,
        target_id: uuid.UUID,
        target_type: str,
        relationship_type: str,
        weight: float = 1.0,
    ) -> KnowledgeRelationshipResponse:
        """Create a new GRC knowledge relationship."""
        rel_id = uuid.uuid4()
        rel = KnowledgeRelationshipResponse(
            relationship_id=rel_id,
            source_id=source_id,
            source_type=source_type,
            target_id=target_id,
            target_type=target_type,
            relationship_type=relationship_type,
            weight=weight,
        )
        cls._relationships[rel_id] = rel
        return rel

    @classmethod
    def get_relationships(cls) -> List[KnowledgeRelationshipResponse]:
        """Get all GRC knowledge relationships."""
        return list(cls._relationships.values())

    @classmethod
    def calculate(cls) -> None:
        """Run relationship mappings (read-only derived intelligence)."""
        pass
