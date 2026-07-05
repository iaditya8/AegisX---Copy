import uuid
from typing import List, Optional
from sqlalchemy.future import select
from src.infrastructure.repositories.base import BaseRepository
from src.infrastructure.database.models import (
    SecurityIntelligenceFabricNode,
    SecurityIntelligenceFabricPropagation,
    SecurityIntelligenceFabricHistory
)

class FabricRepository(BaseRepository[SecurityIntelligenceFabricNode]):
    def __init__(self, session):
        super().__init__(session, SecurityIntelligenceFabricNode)

    async def get(self, id: uuid.UUID) -> Optional[SecurityIntelligenceFabricNode]:
        result = await self.session.execute(
            select(SecurityIntelligenceFabricNode).filter(
                SecurityIntelligenceFabricNode.id == id,
                SecurityIntelligenceFabricNode.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def list(self) -> List[SecurityIntelligenceFabricNode]:
        result = await self.session.execute(
            select(SecurityIntelligenceFabricNode).filter(
                SecurityIntelligenceFabricNode.is_deleted == False
            )
        )
        return list(result.scalars().all())

    async def get_by_fingerprint(self, fingerprint: str) -> Optional[SecurityIntelligenceFabricNode]:
        result = await self.session.execute(
            select(SecurityIntelligenceFabricNode).filter(
                SecurityIntelligenceFabricNode.node_fingerprint == fingerprint,
                SecurityIntelligenceFabricNode.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def save_propagation(self, entry: SecurityIntelligenceFabricPropagation) -> None:
        self.session.add(entry)

    async def list_propagations(self) -> List[SecurityIntelligenceFabricPropagation]:
        result = await self.session.execute(
            select(SecurityIntelligenceFabricPropagation)
        )
        return list(result.scalars().all())

    async def save_history(self, entry: SecurityIntelligenceFabricHistory) -> None:
        self.session.add(entry)

    async def list_history(self, fabric_id: uuid.UUID) -> List[SecurityIntelligenceFabricHistory]:
        result = await self.session.execute(
            select(SecurityIntelligenceFabricHistory).filter(
                SecurityIntelligenceFabricHistory.fabric_id == fabric_id
            )
        )
        return list(result.scalars().all())
