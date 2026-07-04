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

    async def get_relationships(self, knowledge_id: uuid.UUID) -> List[SecurityKnowledgeRelationship]:
        result = await self.session.execute(
            select(SecurityKnowledgeRelationship).filter(
                (SecurityKnowledgeRelationship.source_id == knowledge_id) |
                (SecurityKnowledgeRelationship.target_id == knowledge_id)
            )
        )
        return list(result.scalars().all())

    async def save_relationship(self, relationship: SecurityKnowledgeRelationship) -> None:
        self.session.add(relationship)

    async def get_recommendations(self, knowledge_id: uuid.UUID) -> List[SecurityKnowledgeRecommendation]:
        result = await self.session.execute(
            select(SecurityKnowledgeRecommendation)
            .filter_by(knowledge_id=knowledge_id)
            .order_by(SecurityKnowledgeRecommendation.rank.asc())
        )
        return list(result.scalars().all())

    async def save_recommendation(self, recommendation: SecurityKnowledgeRecommendation) -> None:
        self.session.add(recommendation)

    async def get_history(self, knowledge_id: uuid.UUID) -> List[SecurityKnowledgeHistory]:
        result = await self.session.execute(
            select(SecurityKnowledgeHistory)
            .filter_by(knowledge_id=knowledge_id)
            .order_by(SecurityKnowledgeHistory.timestamp.desc())
        )
        return list(result.scalars().all())

    async def save_history(self, history_entry: SecurityKnowledgeHistory) -> None:
        self.session.add(history_entry)
