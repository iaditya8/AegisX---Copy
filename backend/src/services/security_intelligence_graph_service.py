import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.security_intelligence_graph import (
    NodeType,
    EdgeType,
    GraphComponentStatus,
    GraphNodeResponse,
    GraphEdgeResponse,
)
from src.infrastructure.database.models import Asset
from src.services.graph_node_type_registry import GraphNodeTypeRegistry
from src.services.graph_edge_type_registry import GraphEdgeTypeRegistry
from src.services.graph_relationship_weight_registry import GraphRelationshipWeightRegistry
from src.services.graph_fingerprint_service import GraphFingerprintService
from src.services.graph_history_service import GraphHistoryService


from src.infrastructure.cache.cache_dict import CacheDict


class SecurityIntelligenceGraphService:
    # In-memory graph storage
    _nodes = CacheDict("graph_nodes")
    _edges = CacheDict("graph_edges")
    _node_fingerprint_lookup = CacheDict("graph_node_fingerprints")
    _edge_fingerprint_lookup = CacheDict("graph_edge_fingerprints")

    @classmethod
    def clear_graph(cls) -> None:
        """Clear all nodes, edges, lookup maps, and histories."""
        cls._nodes.clear()
        cls._edges.clear()
        cls._node_fingerprint_lookup.clear()
        cls._edge_fingerprint_lookup.clear()
        GraphHistoryService.clear_history()

    @classmethod
    def _get_uuid(cls, val) -> Optional[uuid.UUID]:
        if isinstance(val, uuid.UUID):
            return val
        if isinstance(val, str):
            try:
                return uuid.UUID(val)
            except ValueError:
                pass
        return None

    @classmethod
    def get_node(cls, node_id: uuid.UUID) -> Optional[GraphNodeResponse]:
        """Retrieve a node by ID."""
        return cls._nodes.get(node_id)

    @classmethod
    def get_edge(cls, edge_id: uuid.UUID) -> Optional[GraphEdgeResponse]:
        """Retrieve an edge by ID."""
        return cls._edges.get(edge_id)

    @classmethod
    def get_all_nodes(cls) -> List[GraphNodeResponse]:
        """Retrieve all nodes in the graph."""
        return list(cls._nodes.values())

    @classmethod
    def get_all_edges(cls) -> List[GraphEdgeResponse]:
        """Retrieve all edges in the graph."""
        return list(cls._edges.values())

    @classmethod
    def create_or_sync_node(
        cls, node_type: NodeType, entity_id: uuid.UUID, scope_id: Optional[uuid.UUID] = None
    ) -> GraphNodeResponse:
        """Create or synchronize a graph node, preserving identity and terminal states."""
        node_type_str = node_type.value if hasattr(node_type, "value") else node_type
        if not GraphNodeTypeRegistry.validate(node_type_str):
            raise ValueError(f"Invalid Node Type: {node_type}")

        node_type_enum = NodeType(node_type_str)

        fingerprint = GraphFingerprintService.generate_node_fingerprint(node_type_str, entity_id)
        existing_id = cls._node_fingerprint_lookup.get(fingerprint)

        if existing_id:
            node = cls._nodes[existing_id]
            if node.status == GraphComponentStatus.DEPRECATED:
                # Terminal State Protection
                return node
            return node

        node_id = uuid.uuid4()
        node = GraphNodeResponse(
            node_id=node_id,
            node_fingerprint=fingerprint,
            node_type=node_type_enum,
            entity_id=entity_id,
            status=GraphComponentStatus.ACTIVE,
            scope_id=scope_id,
        )
        cls._nodes[node_id] = node
        cls._node_fingerprint_lookup[fingerprint] = node_id

        GraphHistoryService.record_event(
            node_id, "NODE_ADDED", f"Graph node added of type {node_type_str} for entity {entity_id}"
        )
        return node

    @classmethod
    def create_or_sync_edge(
        cls,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        edge_type: EdgeType,
        weight: float,
        scope_id: Optional[uuid.UUID] = None,
    ) -> GraphEdgeResponse:
        """Create or synchronize an edge in the security intelligence graph."""
        edge_type_str = edge_type.value if hasattr(edge_type, "value") else edge_type
        if not GraphEdgeTypeRegistry.validate(edge_type_str):
            raise ValueError(f"Invalid Edge Type: {edge_type}")

        edge_type_enum = EdgeType(edge_type_str)

        fingerprint = GraphFingerprintService.generate_edge_fingerprint(source_id, edge_type_str, target_id)
        existing_id = cls._edge_fingerprint_lookup.get(fingerprint)

        if existing_id:
            edge = cls._edges[existing_id]
            if edge.status == GraphComponentStatus.DEPRECATED:
                # Terminal State Protection
                return edge
            if edge.weight != weight:
                old_weight = edge.weight
                edge.weight = weight
                GraphHistoryService.record_event(
                    existing_id, "EDGE_WEIGHT_UPDATED", f"Edge weight updated from {old_weight} to {weight}"
                )
            return edge

        edge_id = uuid.uuid4()
        edge = GraphEdgeResponse(
            edge_id=edge_id,
            edge_fingerprint=fingerprint,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type_enum,
            weight=weight,
            status=GraphComponentStatus.ACTIVE,
            scope_id=scope_id,
        )
        cls._edges[edge_id] = edge
        cls._edge_fingerprint_lookup[fingerprint] = edge_id

        GraphHistoryService.record_event(
            edge_id, "EDGE_ADDED", f"Graph edge added of type {edge_type_str} from {source_id} to {target_id}"
        )
        return edge

    @classmethod
    def deprecate_node(cls, node_id: uuid.UUID) -> GraphNodeResponse:
        """Transition a node to DEPRECATED (terminal state)."""
        node = cls.get_node(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")

        if node.status != GraphComponentStatus.DEPRECATED:
            node.status = GraphComponentStatus.DEPRECATED
            GraphHistoryService.record_event(
                node_id, "DEPRECATED", "Node transitioned to terminal state DEPRECATED"
            )
        return node

    @classmethod
    def deprecate_edge(cls, edge_id: uuid.UUID) -> GraphEdgeResponse:
        """Transition an edge to DEPRECATED (terminal state)."""
        edge = cls.get_edge(edge_id)
        if not edge:
            raise ValueError(f"Edge {edge_id} not found")

        if edge.status != GraphComponentStatus.DEPRECATED:
            edge.status = GraphComponentStatus.DEPRECATED
            GraphHistoryService.record_event(
                edge_id, "DEPRECATED", "Edge transitioned to terminal state DEPRECATED"
            )
        return edge

    @classmethod
    async def rebuild_graph_topology(cls, db: AsyncSession) -> None:
        """Assemble node structures from across active database and in-memory domains."""
        # 1. Assets from DB
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        res_assets = await db.execute(q_assets)
        assets = res_assets.scalars().all()
        for a in assets:
            cls.create_or_sync_node(NodeType.ASSET, a.id, a.scope_id)

        # 2. Risks from CyberRiskQuantificationService
        from src.services.cyber_risk_quantification_service import CyberRiskQuantificationService
        for r in await CyberRiskQuantificationService.get_all_risks():
            cls.create_or_sync_node(NodeType.RISK, r.risk_id, r.scope_id)

        # 3. GRC Compliance Assessments from GovernanceRiskComplianceService
        from src.services.governance_risk_compliance_service import GovernanceRiskComplianceService
        for c in await GovernanceRiskComplianceService.get_all_assessments():
            cls.create_or_sync_node(NodeType.COMPLIANCE, c.assessment_id, c.scope_id)

        # 4. Postures from SecurityPostureService
        from src.services.security_posture_service import SecurityPostureService
        for p in SecurityPostureService.get_all_postures():
            cls.create_or_sync_node(NodeType.POSTURE, p.posture_id, p.scope_id)

        # 5. Resilience records
        from src.services.cyber_resilience_service import CyberResilienceService
        for res in await CyberResilienceService.get_all_resilience():
            cls.create_or_sync_node(NodeType.RESILIENCE, res.resilience_id, res.scope_id)

        # 6. GRC Knowledge items
        from src.services.security_knowledge_service import SecurityKnowledgeService
        for k in await SecurityKnowledgeService.get_all_knowledge():
            cls.create_or_sync_node(NodeType.KNOWLEDGE, k.knowledge_id, k.scope_id)

        # 7. Threat intelligence records
        from src.services.threat_intelligence_service import ThreatIntelligenceService
        for t in ThreatIntelligenceService.get_all_threats():
            cls.create_or_sync_node(NodeType.THREAT_INTEL, t.threat_intel_id, t.scope_id)

        # 8. Incidents
        from src.services.incident_service import IncidentService
        for inc in IncidentService.get_all_incidents():
            scope_id = None
            if inc.asset_ids:
                try:
                    db_asset = await db.get(Asset, inc.asset_ids[0])
                    if db_asset and hasattr(db_asset, "scope_id"):
                        scope_id = cls._get_uuid(db_asset.scope_id)
                except Exception:
                    pass
            cls.create_or_sync_node(NodeType.INCIDENT, inc.incident_id, scope_id)

        # 9. Cases
        from src.services.case_service import CaseService
        for cs in CaseService.get_all_cases():
            scope_id = None
            if cs.asset_ids:
                try:
                    db_asset = await db.get(Asset, cs.asset_ids[0])
                    if db_asset and hasattr(db_asset, "scope_id"):
                        scope_id = cls._get_uuid(db_asset.scope_id)
                except Exception:
                    pass
            cls.create_or_sync_node(NodeType.CASE, cs.case_id, scope_id)

        # 10. Investigations
        from src.services.investigation_service import InvestigationService
        for incident_id, entries in InvestigationService._investigations.items():
            inc = IncidentService.get_incident(incident_id)
            scope_id = None
            if inc and inc.asset_ids:
                try:
                    db_asset = await db.get(Asset, inc.asset_ids[0])
                    if db_asset and hasattr(db_asset, "scope_id"):
                        scope_id = cls._get_uuid(db_asset.scope_id)
                except Exception:
                    pass
            for entry in entries:
                cls.create_or_sync_node(NodeType.INVESTIGATION, entry.entry_id, scope_id)

    @classmethod
    def calculate_centrality(cls) -> Dict[uuid.UUID, float]:
        """Calculate degree centrality metrics deterministically (derived intelligence)."""
        nodes = cls.get_all_nodes()
        edges = cls.get_all_edges()

        centrality = {n.node_id: 0.0 for n in nodes}
        active_nodes = {n.node_id for n in nodes if n.status != GraphComponentStatus.DEPRECATED}

        for e in edges:
            if e.status == GraphComponentStatus.DEPRECATED:
                continue
            if e.source_id in active_nodes and e.target_id in active_nodes:
                centrality[e.source_id] += e.weight
                centrality[e.target_id] += e.weight

        return centrality

    @classmethod
    def find_shortest_path(
        cls, source_id: uuid.UUID, target_id: uuid.UUID
    ) -> List[Tuple[uuid.UUID, uuid.UUID, str, float]]:
        """Dijkstra deterministic pathfinding over active graph topology."""
        nodes = cls.get_all_nodes()
        edges = cls.get_all_edges()

        # Gather adjacency map
        adj: Dict[uuid.UUID, List[Tuple[uuid.UUID, uuid.UUID, str, float]]] = {n.node_id: [] for n in nodes}
        active_nodes = {n.node_id for n in nodes if n.status != GraphComponentStatus.DEPRECATED}

        for e in edges:
            if e.status == GraphComponentStatus.DEPRECATED:
                continue
            if e.source_id in active_nodes and e.target_id in active_nodes:
                adj[e.source_id].append((e.target_id, e.edge_id, e.edge_type.value, e.weight))

        # Dijkstra
        import heapq
        queue = [(0.0, source_id, [])]
        visited = set()

        while queue:
            dist, current, path = heapq.heappop(queue)

            if current in visited:
                continue
            visited.add(current)

            if current == target_id:
                return path

            for neighbor, edge_id, edge_type, weight in adj.get(current, []):
                if neighbor not in visited:
                    new_path = list(path)
                    new_path.append((current, neighbor, edge_type, weight))
                    heapq.heappush(queue, (dist + weight, neighbor, new_path))

        return []
