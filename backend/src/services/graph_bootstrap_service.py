import uuid
from typing import List
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.services.security_intelligence_graph_service import SecurityIntelligenceGraphService
from src.domain.entities.security_intelligence_graph import (
    NodeType,
    EdgeType,
    GraphComponentStatus,
    GraphNodeResponse,
    GraphEdgeResponse,
)


class GraphBootstrapService:
    @classmethod
    async def bootstrap(cls) -> None:
        """Load nodes and edges from PostgreSQL persistence tables on startup to warm L2 cache."""
        async with UnitOfWork(require_tenant=False) as uow:
            db_nodes = await uow.graph_repo.list_nodes()
            db_edges = await uow.graph_repo.list_edges()

            # Warm nodes cache
            for node in db_nodes:
                res = GraphNodeResponse(
                    node_id=node.node_id,
                    node_fingerprint=node.node_fingerprint,
                    node_type=NodeType(node.node_type),
                    entity_id=node.entity_id,
                    status=GraphComponentStatus(node.status),
                    scope_id=node.scope_id,
                    tenant_id=node.tenant_id,
                )
                SecurityIntelligenceGraphService._nodes.set_for_tenant(node.tenant_id, node.node_id, res)
                SecurityIntelligenceGraphService._node_fingerprint_lookup.set_for_tenant(node.tenant_id, node.node_fingerprint, node.node_id)

            # Warm edges cache
            for edge in db_edges:
                res = GraphEdgeResponse(
                    edge_id=edge.edge_id,
                    edge_fingerprint=edge.edge_fingerprint,
                    source_id=edge.source_id,
                    target_id=edge.target_id,
                    edge_type=EdgeType(edge.edge_type),
                    weight=edge.weight,
                    status=GraphComponentStatus(edge.status),
                    scope_id=edge.scope_id,
                    tenant_id=edge.tenant_id,
                )
                SecurityIntelligenceGraphService._edges.set_for_tenant(edge.tenant_id, edge.edge_id, res)
                SecurityIntelligenceGraphService._edge_fingerprint_lookup.set_for_tenant(edge.tenant_id, edge.edge_fingerprint, edge.edge_id)
