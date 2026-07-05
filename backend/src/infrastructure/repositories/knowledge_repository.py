from typing import List, Optional
import uuid
from sqlalchemy.future import select
from src.infrastructure.database.models import (
    SecurityKnowledgeRecord,
    SecurityKnowledgeRelationship,
    SecurityKnowledgeRecommendation,
    SecurityKnowledgeHistory,
)
from src.infrastructure.repositories.base import BaseRepository


class KnowledgeRepository(BaseRepository[SecurityKnowledgeRecord]):
    def __init__(self, session):
        super().__init__(session, SecurityKnowledgeRecord)

    async def get_by_id(self, id: uuid.UUID) -> Optional[SecurityKnowledgeRecord]:
        result = await self.session.execute(
            select(SecurityKnowledgeRecord).filter(
                SecurityKnowledgeRecord.id == id,
                SecurityKnowledgeRecord.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def get_by_fingerprint(self, tenant_id: uuid.UUID, fingerprint: str) -> Optional[SecurityKnowledgeRecord]:
        result = await self.session.execute(
            select(SecurityKnowledgeRecord).filter(
                SecurityKnowledgeRecord.tenant_id == tenant_id,
                SecurityKnowledgeRecord.knowledge_fingerprint == fingerprint,
                SecurityKnowledgeRecord.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def get_relationships(self, knowledge_id: uuid.UUID) -> List[SecurityKnowledgeRelationship]:
        result = await self.session.execute(
            select(SecurityKnowledgeRelationship).filter(
                ((SecurityKnowledgeRelationship.source_id == knowledge_id) |
                 (SecurityKnowledgeRelationship.target_id == knowledge_id)),
                SecurityKnowledgeRelationship.is_deleted == False
            )
        )
        return list(result.scalars().all())

    async def get_knowledge_relationships(self, tenant_id: uuid.UUID) -> List[SecurityKnowledgeRelationship]:
        result = await self.session.execute(
            select(SecurityKnowledgeRelationship).filter(
                SecurityKnowledgeRelationship.tenant_id == tenant_id,
                SecurityKnowledgeRelationship.is_deleted == False
            )
        )
        return list(result.scalars().all())

    async def save_relationship(self, relationship: SecurityKnowledgeRelationship) -> None:
        self.session.add(relationship)

    async def get_recommendations(self, knowledge_id: uuid.UUID) -> List[SecurityKnowledgeRecommendation]:
        result = await self.session.execute(
            select(SecurityKnowledgeRecommendation)
            .filter(
                SecurityKnowledgeRecommendation.knowledge_id == knowledge_id,
                SecurityKnowledgeRecommendation.is_deleted == False
            )
            .order_by(SecurityKnowledgeRecommendation.rank.asc())
        )
        return list(result.scalars().all())

    async def save_recommendation(self, recommendation: SecurityKnowledgeRecommendation) -> None:
        self.session.add(recommendation)

    async def get_history(self, knowledge_id: uuid.UUID) -> List[SecurityKnowledgeHistory]:
        result = await self.session.execute(
            select(SecurityKnowledgeHistory)
            .filter(
                SecurityKnowledgeHistory.knowledge_id == knowledge_id,
                SecurityKnowledgeHistory.is_deleted == False
            )
            .order_by(SecurityKnowledgeHistory.timestamp.desc())
        )
        return list(result.scalars().all())

    async def save_history(self, history_entry: SecurityKnowledgeHistory) -> None:
        self.session.add(history_entry)
