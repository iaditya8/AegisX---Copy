import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.domain.entities.security_intelligence_fabric import (
    FabricIntelligenceNodeResponse,
    FabricStatus,
    FabricPriority,
)
from src.services.intelligence_source_registry import IntelligenceSourceRegistry
from src.services.fabric_fingerprint_service import FabricFingerprintService
from src.services.fabric_history_service import FabricHistoryService
from src.services.confidence_weight_registry import ConfidenceWeightRegistry


from src.infrastructure.cache.cache_dict import CacheDict


class UnifiedSecurityIntelligenceFabricService:
    # in-memory store: node_id -> FabricIntelligenceNodeResponse
    _fabric_nodes = CacheDict("intelligence_fabric")
    # fingerprint -> node_id
    _fingerprint_lookup = CacheDict("intelligence_fabric_fingerprints")

    @classmethod
    def clear_fabric(cls) -> None:
        """Clear all in-memory fabric nodes and history logs."""
        cls._fabric_nodes.clear()
        cls._fingerprint_lookup.clear()
        FabricHistoryService.clear_history()

    @classmethod
    def get_all_fabric_nodes(cls) -> List[FabricIntelligenceNodeResponse]:
        """Retrieve all fabric intelligence nodes currently tracked."""
        return list(cls._fabric_nodes.values())

    @classmethod
    def get_fabric_node(cls, node_id: uuid.UUID) -> Optional[FabricIntelligenceNodeResponse]:
        """Retrieve a specific fabric node by ID."""
        return cls._fabric_nodes.get(node_id)

    @classmethod
    def get_node_by_fingerprint(cls, fingerprint: str) -> Optional[FabricIntelligenceNodeResponse]:
        """Retrieve a fabric node by fingerprint."""
        nid = cls._fingerprint_lookup.get(fingerprint)
        if nid:
            return cls.get_fabric_node(nid)
        return None

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
    def create_or_sync_fabric_node(
        cls,
        source_type: str,
        scope_id: Optional[uuid.UUID] = None,
        priority: FabricPriority = FabricPriority.MEDIUM,
        target_links: Optional[List[uuid.UUID]] = None,
        rules_hash: str = "",
    ) -> FabricIntelligenceNodeResponse:
        """Create or synchronize a fabric node option enforcing terminal state protection."""
        if not IntelligenceSourceRegistry.validate(source_type):
            raise ValueError(f"Invalid Intelligence Source Type: {source_type}")

        val_scope_id = cls._get_uuid(scope_id)

        # Generate stable fingerprint
        fingerprint = FabricFingerprintService.generate_fingerprint(source_type, val_scope_id, rules_hash)

        existing = cls.get_node_by_fingerprint(fingerprint)
        if existing:
            # Enforce Fabric Terminal State Rule: sync cannot reactivate TERMINATED fabric elements
            if existing.status == FabricStatus.TERMINATED:
                return existing

            # Identity preservation
            if target_links:
                existing.target_links = list(set(existing.target_links + target_links))
            
            existing.updated_at = datetime.now(timezone.utc)
            return existing

        # Retrieve weight params
        params = ConfidenceWeightRegistry.get_parameters(source_type)

        # Create new node
        node_id = uuid.uuid4()
        node = FabricIntelligenceNodeResponse(
            node_id=node_id,
            node_fingerprint=fingerprint,
            source_type=source_type.strip().upper(),
            status=FabricStatus.ACTIVE,
            priority=FabricPriority(priority),
            scope_id=val_scope_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            confidence_weights={
                "base_modifier": params.get("modifier", 1.0),
                "decay_factor": params.get("decay", 0.05),
                "current_confidence": 1.0,
            },
            target_links=target_links or [],
        )

        cls._fabric_nodes[node_id] = node
        cls._fingerprint_lookup[fingerprint] = node_id

        # Record history event
        FabricHistoryService.record_event(
            node_id, "FABRIC_CREATED", f"Created fabric node for source: {source_type}"
        )

        return node

    @classmethod
    def suspend_fabric_node(cls, node_id: uuid.UUID) -> FabricIntelligenceNodeResponse:
        """Suspend the fabric node."""
        node = cls.get_fabric_node(node_id)
        if not node:
            raise ValueError(f"Fabric node with ID {node_id} not found")

        # Enforce Fabric Terminal State Rule
        if node.status == FabricStatus.TERMINATED:
            return node

        if node.status != FabricStatus.SUSPENDED:
            node.status = FabricStatus.SUSPENDED
            node.updated_at = datetime.now(timezone.utc)
            FabricHistoryService.record_event(
                node_id, "SUSPENDED", "Fabric node suspended by operator"
            )

        return node

    @classmethod
    def terminate_fabric_node(cls, node_id: uuid.UUID) -> FabricIntelligenceNodeResponse:
        """Terminate the fabric node (terminal state)."""
        node = cls.get_fabric_node(node_id)
        if not node:
            raise ValueError(f"Fabric node with ID {node_id} not found")

        if node.status != FabricStatus.TERMINATED:
            node.status = FabricStatus.TERMINATED
            node.updated_at = datetime.now(timezone.utc)
            FabricHistoryService.record_event(
                node_id, "TERMINATED", "Fabric node terminated by operator"
            )

        return node

    @classmethod
    async def sync_fabric_state(cls, db=None) -> None:
        """Sync fabric nodes and routes from plans, decisions, threat intelligence, and assets."""
        # 1. Threat Intel
        from src.services.threat_intelligence_service import ThreatIntelligenceService
        threats = ThreatIntelligenceService.get_all_threats()
        for t in threats:
            # Sync threat nodes in the fabric
            # Map threat node target links to decisions/assets
            cls.create_or_sync_fabric_node(
                source_type="THREAT_INTEL",
                scope_id=t.scope_id,
                priority=FabricPriority.HIGH,
                target_links=[t.threat_intel_id],
                rules_hash=f"threat_{t.threat_intel_id}",
            )

        # 2. Security Decisions
        from src.services.security_decision_service import SecurityDecisionService
        decisions = SecurityDecisionService.get_all_decisions()
        for d in decisions:
            cls.create_or_sync_fabric_node(
                source_type="RISK",
                scope_id=d.scope_id,
                priority=FabricPriority.MEDIUM,
                target_links=[d.decision_id],
                rules_hash=f"decision_{d.decision_id}",
            )

        # 3. Autonomous Plans
        from src.services.autonomous_security_planning_service import AutonomousSecurityPlanningService
        plans = AutonomousSecurityPlanningService.get_all_plans()
        for p in plans:
            cls.create_or_sync_fabric_node(
                source_type="POSTURE",
                scope_id=p.scope_id,
                priority=FabricPriority.HIGH,
                target_links=[p.plan_id],
                rules_hash=f"plan_{p.plan_id}",
            )
