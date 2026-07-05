import uuid
from typing import Dict, List, Optional
from src.core.tenant import get_current_tenant_id
from src.domain.entities.security_knowledge import KnowledgeRelationshipResponse
from src.infrastructure.database.models import SecurityKnowledgeRelationship, IntelligenceEvent
from src.infrastructure.database.unit_of_work import UnitOfWork


class KnowledgeRelationshipService:
    @classmethod
    def clear_relationships(cls) -> None:
        """Clear all mapped relationships."""
        pass

    @classmethod
    async def add_relationship(
        cls,
        source_id: uuid.UUID,
        source_type: str,
        target_id: uuid.UUID,
        target_type: str,
        relationship_type: str,
        weight: float = 1.0,
        uow: Optional[UnitOfWork] = None,
    ) -> KnowledgeRelationshipResponse:
        """Create a new GRC knowledge relationship."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        
        async def _add(uow_inst: UnitOfWork) -> SecurityKnowledgeRelationship:
            rel = SecurityKnowledgeRelationship(
                id=uuid.uuid4(),
                source_id=source_id,
                source_type=source_type,
                target_id=target_id,
                target_type=target_type,
                relationship_type=relationship_type,
                weight=weight,
                tenant_id=tenant_id,
                version=1
            )
            await uow_inst.knowledge_repo.save_relationship(rel)
            
            # Emit outbox event
            event = IntelligenceEvent(
                tenant_id=tenant_id,
                domain="knowledge",
                entity_id=rel.id,
                event_type="knowledge.relationship.created",
                payload={"id": str(rel.id), "source_id": str(source_id), "target_id": str(target_id)},
                status="pending"
            )
            uow_inst.session.add(event)
            return rel

        if uow:
            db_rel = await _add(uow)
        else:
            async with UnitOfWork() as new_uow:
                db_rel = await _add(new_uow)
                await new_uow.commit()

        return KnowledgeRelationshipResponse(
            relationship_id=db_rel.id,
            source_id=db_rel.source_id,
            source_type=db_rel.source_type,
            target_id=db_rel.target_id,
            target_type=db_rel.target_type,
            relationship_type=db_rel.relationship_type,
            weight=float(db_rel.weight),
        )

    @classmethod
    async def get_relationships(cls) -> List[KnowledgeRelationshipResponse]:
        """Get all GRC knowledge relationships."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            records = await uow.knowledge_repo.get_knowledge_relationships(tenant_id)
            return [
                KnowledgeRelationshipResponse(
                    relationship_id=r.id,
                    source_id=r.source_id,
                    source_type=r.source_type,
                    target_id=r.target_id,
                    target_type=r.target_type,
                    relationship_type=r.relationship_type,
                    weight=float(r.weight),
                )
                for r in records
            ]

    @classmethod
    def calculate(cls) -> None:
        """Run relationship mappings (read-only derived intelligence)."""
        pass
