from typing import List, Optional
import uuid
from sqlalchemy.future import select
from src.core.tenant import get_current_tenant_id
from src.infrastructure.database.models import (
    SecurityIntelligenceNode,
    SecurityIntelligenceEdge,
    SecurityIntelligenceGraphHistory,
)
from src.infrastructure.repositories.base import BaseRepository


class GraphRepository(BaseRepository[SecurityIntelligenceNode]):
    def __init__(self, session):
        super().__init__(session, SecurityIntelligenceNode)

    async def get_node(self, node_id: uuid.UUID) -> Optional[SecurityIntelligenceNode]:
        result = await self.session.execute(
            select(SecurityIntelligenceNode).filter(
                SecurityIntelligenceNode.node_id == node_id,
                SecurityIntelligenceNode.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def get_node_by_fingerprint(self, fingerprint: str) -> Optional[SecurityIntelligenceNode]:
        result = await self.session.execute(
            select(SecurityIntelligenceNode).filter(
                SecurityIntelligenceNode.node_fingerprint == fingerprint,
                SecurityIntelligenceNode.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def list_nodes(self) -> List[SecurityIntelligenceNode]:
        result = await self.session.execute(
            select(SecurityIntelligenceNode).filter(SecurityIntelligenceNode.is_deleted == False)
        )
        return list(result.scalars().all())

    async def save_node(self, node: SecurityIntelligenceNode) -> None:
        self.session.add(node)

    async def get_edge(self, edge_id: uuid.UUID) -> Optional[SecurityIntelligenceEdge]:
        result = await self.session.execute(
            select(SecurityIntelligenceEdge).filter(
                SecurityIntelligenceEdge.edge_id == edge_id,
                SecurityIntelligenceEdge.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def get_edge_by_fingerprint(self, fingerprint: str) -> Optional[SecurityIntelligenceEdge]:
        result = await self.session.execute(
            select(SecurityIntelligenceEdge).filter(
                SecurityIntelligenceEdge.edge_fingerprint == fingerprint,
                SecurityIntelligenceEdge.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def list_edges(self) -> List[SecurityIntelligenceEdge]:
        result = await self.session.execute(
            select(SecurityIntelligenceEdge).filter(SecurityIntelligenceEdge.is_deleted == False)
        )
        return list(result.scalars().all())

    async def save_edge(self, edge: SecurityIntelligenceEdge) -> None:
        self.session.add(edge)

    async def list_neighbors(self, node_id: uuid.UUID) -> List[SecurityIntelligenceNode]:
        edges_res = await self.session.execute(
            select(SecurityIntelligenceEdge).filter(
                SecurityIntelligenceEdge.source_id == node_id,
                SecurityIntelligenceEdge.is_deleted == False
            )
        )
        edges = edges_res.scalars().all()
        target_ids = [e.target_id for e in edges]
        if not target_ids:
            return []
        nodes_res = await self.session.execute(
            select(SecurityIntelligenceNode).filter(
                SecurityIntelligenceNode.node_id.in_(target_ids),
                SecurityIntelligenceNode.is_deleted == False
            )
        )
        return list(nodes_res.scalars().all())

    async def get_relationships(self, node_id: uuid.UUID) -> List[SecurityIntelligenceEdge]:
        result = await self.session.execute(
            select(SecurityIntelligenceEdge).filter(
                ((SecurityIntelligenceEdge.source_id == node_id) |
                 (SecurityIntelligenceEdge.target_id == node_id)),
                SecurityIntelligenceEdge.is_deleted == False
            )
        )
        return list(result.scalars().all())

    async def save_history(self, history_entry: SecurityIntelligenceGraphHistory) -> None:
        self.session.add(history_entry)

    async def get_history(self, component_id: uuid.UUID) -> List[SecurityIntelligenceGraphHistory]:
        result = await self.session.execute(
            select(SecurityIntelligenceGraphHistory)
            .filter_by(component_id=component_id)
            .order_by(SecurityIntelligenceGraphHistory.created_at.desc())
        )
        return list(result.scalars().all())
