import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.security_intelligence_fabric import (
    FabricIntelligenceNodeResponse,
    FabricStatus,
    FabricPriority,
)
from src.services.intelligence_source_registry import IntelligenceSourceRegistry
from src.services.fabric_fingerprint_service import FabricFingerprintService
from src.services.fabric_history_service import FabricHistoryService
from src.services.confidence_weight_registry import ConfidenceWeightRegistry
from src.infrastructure.cache.tenant_cache_dict import TenantCacheDict
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import (
    SecurityIntelligenceFabricNode as DBNode,
    IntelligenceEvent,
)
from src.core.tenant import get_current_tenant_id, require_current_tenant_id


class UnifiedSecurityIntelligenceFabricService:
    # L2 caches
    _fabric_nodes = TenantCacheDict("intelligence_fabric")
    _fingerprint_lookup = TenantCacheDict("intelligence_fabric_fingerprints")

    @classmethod
    def clear_fabric(cls) -> None:
        """Clear all in-memory fabric nodes and history logs."""
        cls._fabric_nodes.clear()
        cls._fingerprint_lookup.clear()
        FabricHistoryService.clear_history()

    @classmethod
    async def bootstrap(cls, db: AsyncSession) -> None:
        """Bootstrap L2 cache — loads ALL tenants but stores with tenant_id."""
        cls.clear_fabric()
        async with UnitOfWork(require_tenant=False) as uow:
            db_nodes = await uow.fabric_repo.list()
            for db_n in db_nodes:
                node = FabricIntelligenceNodeResponse(
                    node_id=db_n.id,
                    tenant_id=db_n.tenant_id,
                    node_fingerprint=db_n.node_fingerprint,
                    source_type=db_n.source_type,
                    status=FabricStatus(db_n.status),
                    priority=FabricPriority(db_n.priority),
                    scope_id=db_n.scope_id,
                    created_at=db_n.created_at,
                    updated_at=db_n.updated_at,
                    confidence_weights=db_n.confidence_weights,
                    target_links=db_n.target_links,
                )
                cls._fabric_nodes.set_for_tenant(db_n.tenant_id, db_n.id, node)
                cls._fingerprint_lookup.set_for_tenant(db_n.tenant_id, db_n.node_fingerprint, db_n.id)

    @classmethod
    def get_all_fabric_nodes(cls) -> List[FabricIntelligenceNodeResponse]:
        """Retrieve fabric nodes for the current tenant only."""
        tenant_id = require_current_tenant_id()
        return [n for n in cls._fabric_nodes.values() if n.tenant_id == tenant_id]

    @classmethod
    def get_fabric_node(cls, node_id: uuid.UUID) -> Optional[FabricIntelligenceNodeResponse]:
        """Retrieve a specific fabric node by ID with tenant validation."""
        tenant_id = require_current_tenant_id()
        node = cls._fabric_nodes.get(node_id)
        if node and node.tenant_id == tenant_id:
            return node
        return None

    @classmethod
    def get_node_by_fingerprint(cls, fingerprint: str) -> Optional[FabricIntelligenceNodeResponse]:
        """Retrieve a fabric node by fingerprint with tenant validation."""
        tenant_id = require_current_tenant_id()
        nid = cls._fingerprint_lookup.get(fingerprint)
        if nid:
            node = cls._fabric_nodes.get(nid)
            if node and node.tenant_id == tenant_id:
                return node
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
    async def create_or_sync_fabric_node(
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
        fingerprint = FabricFingerprintService.generate_fingerprint(source_type, val_scope_id, rules_hash)

        existing = cls.get_node_by_fingerprint(fingerprint)
        tenant_id = require_current_tenant_id()

        if existing:
            if existing.status == FabricStatus.TERMINATED:
                return existing

            changed = False
            if target_links:
                new_links = list(set(existing.target_links + target_links))
                if len(new_links) != len(existing.target_links):
                    existing.target_links = new_links
                    changed = True

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
                async with UnitOfWork() as uow:
                    db_n = await uow.fabric_repo.get(existing.node_id)
                    if db_n:
                        db_n.target_links = existing.target_links
                        db_n.updated_at = existing.updated_at
                        await FabricHistoryService.record_event(
                            existing.node_id,
                            "FABRIC_UPDATED",
                            f"Updated fabric node link associations: {existing.target_links}",
                            uow=uow,
                        )
                        # Stage outbox event
                        outbox_evt = IntelligenceEvent(
                            tenant_id=tenant_id,
                            event_type="fabric.updated",
                            payload={
                                "node_id": str(existing.node_id),
                                "status": existing.status.value,
                            }
                        )
                        uow.session.add(outbox_evt)
                        await uow.commit()

            return existing

        params = ConfidenceWeightRegistry.get_parameters(source_type)
        node_id = uuid.uuid4()
        node = FabricIntelligenceNodeResponse(
            node_id=node_id,
            tenant_id=tenant_id,
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

        async with UnitOfWork() as uow:
            db_n = DBNode(
                tenant_id=tenant_id,
                id=node_id,
                node_fingerprint=fingerprint,
                source_type=node.source_type,
                status=FabricStatus.ACTIVE.value,
                priority=priority.value,
                scope_id=val_scope_id,
                confidence_weights=node.confidence_weights,
                target_links=node.target_links,
            )
            await uow.fabric_repo.save(db_n)
            await uow.session.flush()
            await FabricHistoryService.record_event(
                node_id, "FABRIC_CREATED", f"Created fabric node for source: {source_type}", uow=uow
            )
            # Stage outbox event
            outbox_evt = IntelligenceEvent(
                tenant_id=tenant_id,
                event_type="fabric.created",
                payload={
                    "node_id": str(node_id),
                    "status": FabricStatus.ACTIVE.value,
                }
            )
            uow.session.add(outbox_evt)
            await uow.commit()

        return node

    @classmethod
    async def suspend_fabric_node(cls, node_id: uuid.UUID) -> FabricIntelligenceNodeResponse:
        """Suspend the fabric node."""
        node = cls.get_fabric_node(node_id)
        if not node:
            raise ValueError(f"Fabric node with ID {node_id} not found")

        if node.status == FabricStatus.TERMINATED:
            return node

        if node.status != FabricStatus.SUSPENDED:
            node.status = FabricStatus.SUSPENDED
            node.updated_at = datetime.now(timezone.utc)
            tenant_id = require_current_tenant_id()
            async with UnitOfWork() as uow:
                db_n = await uow.fabric_repo.get(node_id)
                if db_n:
                    db_n.status = FabricStatus.SUSPENDED.value
                    db_n.updated_at = node.updated_at
                    await FabricHistoryService.record_event(
                        node_id, "SUSPENDED", "Fabric node suspended by operator", uow=uow
                    )
                    # Stage outbox event
                    outbox_evt = IntelligenceEvent(
                        tenant_id=tenant_id,
                        event_type="fabric.suspended",
                        payload={
                            "node_id": str(node_id),
                            "status": FabricStatus.SUSPENDED.value,
                        }
                    )
                    uow.session.add(outbox_evt)
                    await uow.commit()

        return node

    @classmethod
    async def terminate_fabric_node(cls, node_id: uuid.UUID) -> FabricIntelligenceNodeResponse:
        """Terminate the fabric node (terminal state)."""
        node = cls.get_fabric_node(node_id)
        if not node:
            raise ValueError(f"Fabric node with ID {node_id} not found")

        if node.status != FabricStatus.TERMINATED:
            node.status = FabricStatus.TERMINATED
            node.updated_at = datetime.now(timezone.utc)
            tenant_id = require_current_tenant_id()
            async with UnitOfWork() as uow:
                db_n = await uow.fabric_repo.get(node_id)
                if db_n:
                    db_n.status = FabricStatus.TERMINATED.value
                    db_n.updated_at = node.updated_at
                    await FabricHistoryService.record_event(
                        node_id, "TERMINATED", "Fabric node terminated by operator", uow=uow
                    )
                    # Stage outbox event
                    outbox_evt = IntelligenceEvent(
                        tenant_id=tenant_id,
                        event_type="fabric.terminated",
                        payload={
                            "node_id": str(node_id),
                            "status": FabricStatus.TERMINATED.value,
                        }
                    )
                    uow.session.add(outbox_evt)
                    await uow.commit()

        return node

    @classmethod
    async def sync_fabric_state(cls, db=None) -> None:
        """Sync fabric nodes and routes from plans, decisions, threat intelligence, and assets."""
        tenant_id = require_current_tenant_id()

        # 1. Threat Intel
        from src.services.threat_intelligence_service import ThreatIntelligenceService
        threats = ThreatIntelligenceService.get_all_threats()
        for t in threats:
            if getattr(t, "tenant_id", None) != tenant_id:
                continue
            await cls.create_or_sync_fabric_node(
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
            if getattr(d, "tenant_id", None) != tenant_id:
                continue
            await cls.create_or_sync_fabric_node(
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
            if getattr(p, "tenant_id", None) != tenant_id:
                continue
            await cls.create_or_sync_fabric_node(
                source_type="POSTURE",
                scope_id=p.scope_id,
                priority=FabricPriority.HIGH,
                target_links=[p.plan_id],
                rules_hash=f"plan_{p.plan_id}",
            )
