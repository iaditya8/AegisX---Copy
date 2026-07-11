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


from src.infrastructure.cache.tenant_cache_dict import TenantCacheDict
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import (
    SecurityIntelligenceNode,
    SecurityIntelligenceEdge,
    IntelligenceEvent,
)
from src.core.tenant import get_current_tenant_id, require_current_tenant_id


class SecurityIntelligenceGraphService:
    # L2 caches
    _nodes = TenantCacheDict("graph_nodes")
    _edges = TenantCacheDict("graph_edges")
    _node_fingerprint_lookup = TenantCacheDict("graph_node_fingerprints")
    _edge_fingerprint_lookup = TenantCacheDict("graph_edge_fingerprints")

    @classmethod
    def clear_graph(cls) -> None:
        """Clear L2 cache and history."""
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
        """Retrieve a node by ID (L2 cache check)."""
        tenant_id = require_current_tenant_id()
        cached = cls._nodes.get(node_id)
        if cached and cached.tenant_id == tenant_id:
            return cached
        return None

    @classmethod
    def get_edge(cls, edge_id: uuid.UUID) -> Optional[GraphEdgeResponse]:
        """Retrieve an edge by ID (L2 cache check)."""
        tenant_id = require_current_tenant_id()
        cached = cls._edges.get(edge_id)
        if cached and cached.tenant_id == tenant_id:
            return cached
        return None

    @classmethod
    def get_all_nodes(cls) -> List[GraphNodeResponse]:
        """Retrieve all nodes in the graph (L2 cache tenant filtered)."""
        tenant_id = require_current_tenant_id()
        return [r for r in cls._nodes.values() if r.tenant_id == tenant_id]

    @classmethod
    def get_all_edges(cls) -> List[GraphEdgeResponse]:
        """Retrieve all edges in the graph (L2 cache tenant filtered)."""
        tenant_id = require_current_tenant_id()
        return [r for r in cls._edges.values() if r.tenant_id == tenant_id]

    @classmethod
    def _db_node_to_response(cls, node: SecurityIntelligenceNode) -> GraphNodeResponse:
        return GraphNodeResponse(
            node_id=node.node_id,
            node_fingerprint=node.node_fingerprint,
            node_type=NodeType(node.node_type),
            entity_id=node.entity_id,
            status=GraphComponentStatus(node.status),
            scope_id=node.scope_id,
            tenant_id=node.tenant_id,
        )

    @classmethod
    def _db_edge_to_response(cls, edge: SecurityIntelligenceEdge) -> GraphEdgeResponse:
        return GraphEdgeResponse(
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

    @classmethod
    async def create_or_sync_node(
        cls, node_type: NodeType, entity_id: uuid.UUID, scope_id: Optional[uuid.UUID] = None, uow: Optional[UnitOfWork] = None
    ) -> GraphNodeResponse:
        """Create or synchronize a graph node, preserving identity and terminal states."""
        node_type_str = node_type.value if hasattr(node_type, "value") else node_type
        if not GraphNodeTypeRegistry.validate(node_type_str):
            raise ValueError(f"Invalid Node Type: {node_type}")

        tenant_id = require_current_tenant_id()
        fingerprint = GraphFingerprintService.generate_node_fingerprint(node_type_str, entity_id)

        async def _sync(uow_inst: UnitOfWork) -> SecurityIntelligenceNode:
            existing = await uow_inst.graph_repo.get_node_by_fingerprint(fingerprint)
            if existing:
                return existing

            node_id = uuid.uuid4()
            db_node = SecurityIntelligenceNode(
                node_id=node_id,
                node_fingerprint=fingerprint,
                node_type=node_type_str,
                entity_id=entity_id,
                status=GraphComponentStatus.ACTIVE.value,
                scope_id=scope_id,
                tenant_id=tenant_id,
                version=1
            )
            await uow_inst.graph_repo.save_node(db_node)
            await uow_inst.session.flush()

            await GraphHistoryService.record_event(
                node_id, "NODE_ADDED", f"Graph node added of type {node_type_str} for entity {entity_id}", uow=uow_inst
            )

            event = IntelligenceEvent(
                tenant_id=tenant_id,
                domain="graph",
                entity_id=node_id,
                event_type="graph.node.added",
                payload={"node_id": str(node_id), "node_type": node_type_str, "entity_id": str(entity_id)},
                status="pending"
            )
            uow_inst.session.add(event)
            return db_node

        if uow:
            db_node = await _sync(uow)
        else:
            async with UnitOfWork() as new_uow:
                db_node = await _sync(new_uow)
                await new_uow.commit()

        # Warm L2 cache
        res = cls._db_node_to_response(db_node)
        cls._nodes[db_node.node_id] = res
        cls._node_fingerprint_lookup[db_node.node_fingerprint] = db_node.node_id

        return res

    @classmethod
    async def create_or_sync_edge(
        cls,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        edge_type: EdgeType,
        weight: float,
        scope_id: Optional[uuid.UUID] = None,
        uow: Optional[UnitOfWork] = None,
    ) -> GraphEdgeResponse:
        """Create or synchronize an edge in the security intelligence graph."""
        edge_type_str = edge_type.value if hasattr(edge_type, "value") else edge_type
        if not GraphEdgeTypeRegistry.validate(edge_type_str):
            raise ValueError(f"Invalid Edge Type: {edge_type}")

        tenant_id = require_current_tenant_id()
        
        source_node = cls.get_node(source_id)
        target_node = cls.get_node(target_id)
        if not source_node:
            from src.core.tenant import TenantMismatchError
            raise TenantMismatchError(f"Source node {source_id} not found in the current tenant context")
        if not target_node:
            from src.core.tenant import TenantMismatchError
            raise TenantMismatchError(f"Target node {target_id} not found in the current tenant context")
        fingerprint = GraphFingerprintService.generate_edge_fingerprint(source_id, edge_type_str, target_id)

        async def _sync(uow_inst: UnitOfWork) -> SecurityIntelligenceEdge:
            existing = await uow_inst.graph_repo.get_edge_by_fingerprint(fingerprint)
            if existing:
                if existing.status == GraphComponentStatus.DEPRECATED.value:
                    return existing
                if existing.weight != weight:
                    old_weight = existing.weight
                    existing.weight = weight
                    existing.updated_at = datetime.now(timezone.utc)
                    await GraphHistoryService.record_event(
                        existing.edge_id, "EDGE_WEIGHT_UPDATED", f"Edge weight updated from {old_weight} to {weight}", uow=uow_inst
                    )
                return existing

            edge_id = uuid.uuid4()
            db_edge = SecurityIntelligenceEdge(
                edge_id=edge_id,
                edge_fingerprint=fingerprint,
                source_id=source_id,
                target_id=target_id,
                edge_type=edge_type_str,
                weight=weight,
                status=GraphComponentStatus.ACTIVE.value,
                scope_id=scope_id,
                tenant_id=tenant_id,
                version=1
            )
            await uow_inst.graph_repo.save_edge(db_edge)
            await uow_inst.session.flush()

            await GraphHistoryService.record_event(
                edge_id, "EDGE_ADDED", f"Graph edge added of type {edge_type_str} from {source_id} to {target_id}", uow=uow_inst
            )

            event = IntelligenceEvent(
                tenant_id=tenant_id,
                domain="graph",
                entity_id=edge_id,
                event_type="graph.edge.added",
                payload={"edge_id": str(edge_id), "source_id": str(source_id), "target_id": str(target_id), "edge_type": edge_type_str},
                status="pending"
            )
            uow_inst.session.add(event)
            return db_edge

        if uow:
            db_edge = await _sync(uow)
        else:
            async with UnitOfWork() as new_uow:
                db_edge = await _sync(new_uow)
                await new_uow.commit()

        # Warm L2 cache
        res = cls._db_edge_to_response(db_edge)
        cls._edges[db_edge.edge_id] = res
        cls._edge_fingerprint_lookup[db_edge.edge_fingerprint] = db_edge.edge_id

        return res

    @classmethod
    async def deprecate_node(cls, node_id: uuid.UUID) -> GraphNodeResponse:
        """Transition a node to DEPRECATED (terminal state)."""
        tenant_id = require_current_tenant_id()
        async with UnitOfWork() as uow:
            node = await uow.graph_repo.get_node(node_id)
            if not node:
                raise ValueError(f"Node {node_id} not found")

            if node.status != GraphComponentStatus.DEPRECATED.value:
                node.status = GraphComponentStatus.DEPRECATED.value
                node.updated_at = datetime.now(timezone.utc)
                await GraphHistoryService.record_event(
                    node_id, "DEPRECATED", "Node transitioned to terminal state DEPRECATED", uow=uow
                )

                event = IntelligenceEvent(
                    tenant_id=tenant_id,
                    domain="graph",
                    entity_id=node_id,
                    event_type="graph.node.deprecated",
                    payload={"node_id": str(node_id)},
                    status="pending"
                )
                uow.session.add(event)
                await uow.commit()

            # Warm L2 cache
            res = cls._db_node_to_response(node)
            cls._nodes[node.node_id] = res
            cls._node_fingerprint_lookup[node.node_fingerprint] = node.node_id

            return res

    @classmethod
    async def deprecate_edge(cls, edge_id: uuid.UUID) -> GraphEdgeResponse:
        """Transition an edge to DEPRECATED (terminal state)."""
        tenant_id = require_current_tenant_id()
        async with UnitOfWork() as uow:
            edge = await uow.graph_repo.get_edge(edge_id)
            if not edge:
                raise ValueError(f"Edge {edge_id} not found")

            if edge.status != GraphComponentStatus.DEPRECATED.value:
                edge.status = GraphComponentStatus.DEPRECATED.value
                edge.updated_at = datetime.now(timezone.utc)
                await GraphHistoryService.record_event(
                    edge_id, "DEPRECATED", "Edge transitioned to terminal state DEPRECATED", uow=uow
                )

                event = IntelligenceEvent(
                    tenant_id=tenant_id,
                    domain="graph",
                    entity_id=edge_id,
                    event_type="graph.edge.deprecated",
                    payload={"edge_id": str(edge_id)},
                    status="pending"
                )
                uow.session.add(event)
                await uow.commit()

            # Warm L2 cache
            res = cls._db_edge_to_response(edge)
            cls._edges[edge.edge_id] = res
            cls._edge_fingerprint_lookup[edge.edge_fingerprint] = edge.edge_id

            return res

    @classmethod
    async def rebuild_graph_topology(cls, db: AsyncSession) -> None:
        """Assemble node structures from across active database and in-memory domains."""
        tenant_id = require_current_tenant_id()

        # 1. Assets from DB
        q_assets = select(Asset).where(
            Asset.deleted_at.is_(None),
            Asset.tenant_id == tenant_id
        )
        res_assets = await db.execute(q_assets)
        assets = res_assets.scalars().all()
        for a in assets:
            await cls.create_or_sync_node(NodeType.ASSET, a.id, a.scope_id)

        # 2. Risks from CyberRiskQuantificationService
        from src.services.cyber_risk_quantification_service import CyberRiskQuantificationService
        for r in await CyberRiskQuantificationService.get_all_risks():
            if getattr(r, "tenant_id", None) != tenant_id:
                continue
            await cls.create_or_sync_node(NodeType.RISK, r.risk_id, r.scope_id)

        # 3. GRC Compliance Assessments from GovernanceRiskComplianceService
        from src.services.governance_risk_compliance_service import GovernanceRiskComplianceService
        for c in await GovernanceRiskComplianceService.get_all_assessments():
            if getattr(c, "tenant_id", None) != tenant_id:
                continue
            await cls.create_or_sync_node(NodeType.COMPLIANCE, c.assessment_id, c.scope_id)

        # 4. Postures from SecurityPostureService
        from src.services.security_posture_service import SecurityPostureService
        for p in SecurityPostureService.get_all_postures():
            if getattr(p, "tenant_id", None) != tenant_id:
                continue
            await cls.create_or_sync_node(NodeType.POSTURE, p.posture_id, p.scope_id)

        # 5. Resilience records
        from src.services.cyber_resilience_service import CyberResilienceService
        for res in await CyberResilienceService.get_all_resilience():
            if getattr(res, "tenant_id", None) != tenant_id:
                continue
            await cls.create_or_sync_node(NodeType.RESILIENCE, res.resilience_id, res.scope_id)

        # 6. GRC Knowledge items
        from src.services.security_knowledge_service import SecurityKnowledgeService
        for k in await SecurityKnowledgeService.get_all_knowledge():
            if getattr(k, "tenant_id", None) != tenant_id:
                continue
            await cls.create_or_sync_node(NodeType.KNOWLEDGE, k.knowledge_id, k.scope_id)

        # 7. Threat intelligence records
        from src.services.threat_intelligence_service import ThreatIntelligenceService
        for t in ThreatIntelligenceService.get_all_threats():
            if getattr(t, "tenant_id", None) != tenant_id:
                continue
            await cls.create_or_sync_node(NodeType.THREAT_INTEL, t.threat_intel_id, t.scope_id)

        # 8. Incidents
        from src.services.incident_service import IncidentService
        for inc in IncidentService.get_all_incidents():
            if getattr(inc, "tenant_id", None) != tenant_id:
                continue
            scope_id = None
            if inc.asset_ids:
                try:
                    db_asset = await db.get(Asset, inc.asset_ids[0])
                    if db_asset and hasattr(db_asset, "scope_id"):
                        scope_id = cls._get_uuid(db_asset.scope_id)
                except Exception:
                    pass
            await cls.create_or_sync_node(NodeType.INCIDENT, inc.incident_id, scope_id)

        # 9. Cases
        from src.services.case_service import CaseService
        for cs in CaseService.get_all_cases():
            if getattr(cs, "tenant_id", None) != tenant_id:
                continue
            scope_id = None
            if cs.asset_ids:
                try:
                    db_asset = await db.get(Asset, cs.asset_ids[0])
                    if db_asset and hasattr(db_asset, "scope_id"):
                        scope_id = cls._get_uuid(db_asset.scope_id)
                except Exception:
                    pass
            await cls.create_or_sync_node(NodeType.CASE, cs.case_id, scope_id)

        # 10. Investigations
        from src.services.investigation_service import InvestigationService
        for incident_id, entries in InvestigationService._investigations.items():
            inc = IncidentService.get_incident(incident_id)
            if not inc or getattr(inc, "tenant_id", None) != tenant_id:
                continue
            scope_id = None
            if inc.asset_ids:
                try:
                    db_asset = await db.get(Asset, inc.asset_ids[0])
                    if db_asset and hasattr(db_asset, "scope_id"):
                        scope_id = cls._get_uuid(db_asset.scope_id)
                except Exception:
                    pass
            for entry in entries:
                await cls.create_or_sync_node(NodeType.INVESTIGATION, entry.entry_id, scope_id)

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

        adj: Dict[uuid.UUID, List[Tuple[uuid.UUID, uuid.UUID, str, float]]] = {n.node_id: [] for n in nodes}
        active_nodes = {n.node_id for n in nodes if n.status != GraphComponentStatus.DEPRECATED}

        for e in edges:
            if e.status == GraphComponentStatus.DEPRECATED:
                continue
            if e.source_id in active_nodes and e.target_id in active_nodes:
                adj[e.source_id].append((e.target_id, e.edge_id, e.edge_type.value, e.weight))

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
