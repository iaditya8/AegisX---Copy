import uuid
from typing import Dict, List, Optional

from src.domain.entities.security_intelligence_graph import EdgeType, NodeType, GraphComponentStatus
from src.services.graph_relationship_weight_registry import GraphRelationshipWeightRegistry


class GraphCorrelationService:
    @classmethod
    async def recalculate_cross_domain_links(cls) -> None:
        """Trace cross-domain alignments and generate edges deterministically (derived intelligence)."""
        from src.services.security_intelligence_graph_service import SecurityIntelligenceGraphService

        # 1. Remove all active non-deprecated edges to rebuild cleanly
        active_edge_ids = [
            e.edge_id for e in SecurityIntelligenceGraphService.get_all_edges()
            if e.status != GraphComponentStatus.DEPRECATED
        ]
        for eid in active_edge_ids:
            SecurityIntelligenceGraphService._edges.pop(eid, None)
            
        # Re-initialize fingerprint lookup for surviving edges
        SecurityIntelligenceGraphService._edge_fingerprint_lookup = {
            e.edge_fingerprint: e.edge_id
            for e in SecurityIntelligenceGraphService.get_all_edges()
        }

        # Gather nodes by type
        nodes = SecurityIntelligenceGraphService.get_all_nodes()
        nodes_by_type = {}
        for n in nodes:
            nodes_by_type.setdefault(n.node_type, []).append(n)

        # A. Incidents to Cases (CONTAINED_IN)
        from src.services.case_service import CaseService
        cases = CaseService.get_all_cases()
        for cs in cases:
            case_node = cls._find_node_by_entity(nodes_by_type.get(NodeType.CASE, []), cs.case_id)
            if not case_node:
                continue
            for iid in cs.incident_ids:
                inc_node = cls._find_node_by_entity(nodes_by_type.get(NodeType.INCIDENT, []), iid)
                if inc_node:
                    w = GraphRelationshipWeightRegistry.get_weight(EdgeType.CONTAINED_IN)
                    await SecurityIntelligenceGraphService.create_or_sync_edge(
                        inc_node.node_id, case_node.node_id, EdgeType.CONTAINED_IN, w, case_node.scope_id
                    )

        # B. Postures to Assets (AFFECTS)
        from src.services.security_posture_service import SecurityPostureService
        postures = SecurityPostureService.get_all_postures()
        for p in postures:
            p_node = cls._find_node_by_entity(nodes_by_type.get(NodeType.POSTURE, []), p.posture_id)
            a_node = cls._find_node_by_entity(nodes_by_type.get(NodeType.ASSET, []), p.asset_id)
            if p_node and a_node:
                w = GraphRelationshipWeightRegistry.get_weight(EdgeType.AFFECTS)
                await SecurityIntelligenceGraphService.create_or_sync_edge(
                    p_node.node_id, a_node.node_id, EdgeType.AFFECTS, w, p.scope_id
                )

        # C. Investigations to Incidents (CONTAINED_IN)
        from src.services.investigation_service import InvestigationService
        for incident_id, entries in InvestigationService._investigations.items():
            inc_node = cls._find_node_by_entity(nodes_by_type.get(NodeType.INCIDENT, []), incident_id)
            if not inc_node:
                continue
            for entry in entries:
                inv_node = cls._find_node_by_entity(nodes_by_type.get(NodeType.INVESTIGATION, []), entry.entry_id)
                if inv_node:
                    w = GraphRelationshipWeightRegistry.get_weight(EdgeType.CONTAINED_IN)
                    await SecurityIntelligenceGraphService.create_or_sync_edge(
                        inv_node.node_id, inc_node.node_id, EdgeType.CONTAINED_IN, w, inc_node.scope_id
                    )

        # D. Threat Intel to GRC Knowledge (MITIGATES)
        from src.services.threat_intelligence_service import ThreatIntelligenceService
        from src.services.security_knowledge_service import SecurityKnowledgeService
        threats = ThreatIntelligenceService.get_all_threats()
        knows = await SecurityKnowledgeService.get_all_knowledge()
        for t in threats:
            t_node = cls._find_node_by_entity(nodes_by_type.get(NodeType.THREAT_INTEL, []), t.threat_intel_id)
            if not t_node:
                continue
            for k in knows:
                k_node = cls._find_node_by_entity(nodes_by_type.get(NodeType.KNOWLEDGE, []), k.knowledge_id)
                if not k_node:
                    continue
                shared_tags = set(t.tags) & set(k.tags)
                if shared_tags:
                    w = GraphRelationshipWeightRegistry.get_weight(EdgeType.MITIGATES)
                    await SecurityIntelligenceGraphService.create_or_sync_edge(
                        k_node.node_id, t_node.node_id, EdgeType.MITIGATES, w, t.scope_id
                    )

    @classmethod
    def _find_node_by_entity(cls, node_list: list, entity_id: uuid.UUID):
        for n in node_list:
            if n.entity_id == entity_id:
                return n
        return None
