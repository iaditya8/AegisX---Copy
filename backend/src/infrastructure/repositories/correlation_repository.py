from typing import List, Optional
import uuid
from sqlalchemy.future import select
from src.infrastructure.database.models import (
    CorrelationRule,
    CorrelationCluster,
    CorrelationClusterSignal,
    CorrelationHistory,
    CorrelationRuleMatch,
)
from src.infrastructure.repositories.base import BaseRepository


class CorrelationRepository(BaseRepository[CorrelationCluster]):
    def __init__(self, session):
        super().__init__(session, CorrelationCluster)

    async def find_active_rules(self) -> List[CorrelationRule]:
        tenant_id = self._get_tenant_id()
        query = select(CorrelationRule).filter(
            CorrelationRule.tenant_id == tenant_id,
            CorrelationRule.status == "active"
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_clusters_by_tenant(self) -> List[CorrelationCluster]:
        tenant_id = self._get_tenant_id()
        query = select(CorrelationCluster).filter(
            CorrelationCluster.tenant_id == tenant_id
        ).order_by(CorrelationCluster.unified_score.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_cluster_by_fingerprint(self, fingerprint: str) -> Optional[CorrelationCluster]:
        tenant_id = self._get_tenant_id()
        query = select(CorrelationCluster).filter(
            CorrelationCluster.tenant_id == tenant_id,
            CorrelationCluster.fingerprint == fingerprint
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def add_signal_to_cluster(self, cluster_id: uuid.UUID, signal_type: str, signal_id: uuid.UUID) -> None:
        tenant_id = self._get_tenant_id()
        # Check if relationship already exists to satisfy uq_cluster_signal
        query = select(CorrelationClusterSignal).filter(
            CorrelationClusterSignal.cluster_id == cluster_id,
            CorrelationClusterSignal.signal_type == signal_type,
            CorrelationClusterSignal.signal_id == signal_id
        )
        existing = await self.session.execute(query)
        if not existing.scalar_one_or_none():
            signal = CorrelationClusterSignal(
                id=uuid.uuid4(),
                cluster_id=cluster_id,
                signal_type=signal_type,
                signal_id=signal_id,
                tenant_id=tenant_id
            )
            self.session.add(signal)

    async def append_history(self, cluster_id: uuid.UUID, event_type: str, details: dict) -> None:
        tenant_id = self._get_tenant_id()
        history_entry = CorrelationHistory(
            id=uuid.uuid4(),
            cluster_id=cluster_id,
            event_type=event_type,
            details_json=details,
            tenant_id=tenant_id
        )
        self.session.add(history_entry)

    async def save_rule_match(self, rule_id: uuid.UUID, rule_version_used: int, cluster_id: uuid.UUID, confidence: float, evidence: dict) -> None:
        tenant_id = self._get_tenant_id()
        match_entry = CorrelationRuleMatch(
            id=uuid.uuid4(),
            rule_id=rule_id,
            rule_version_used=rule_version_used,
            cluster_id=cluster_id,
            confidence=confidence,
            evidence_json=evidence,
            tenant_id=tenant_id
        )
        self.session.add(match_entry)

    async def list_rule_matches_for_cluster(self, cluster_id: uuid.UUID) -> List[CorrelationRuleMatch]:
        tenant_id = self._get_tenant_id()
        query = select(CorrelationRuleMatch).filter(
            CorrelationRuleMatch.tenant_id == tenant_id,
            CorrelationRuleMatch.cluster_id == cluster_id
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_rule(self, id: uuid.UUID) -> Optional[CorrelationRule]:
        tenant_id = self._get_tenant_id()
        query = select(CorrelationRule).filter(
            CorrelationRule.tenant_id == tenant_id,
            CorrelationRule.id == id
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def save_rule(self, rule: CorrelationRule) -> None:
        tenant_id = self._get_tenant_id()
        if rule.tenant_id is None:
            rule.tenant_id = tenant_id
        self.session.add(rule)

    async def save_cluster(self, cluster: CorrelationCluster) -> None:
        tenant_id = self._get_tenant_id()
        if cluster.tenant_id is None:
            cluster.tenant_id = tenant_id
        self.session.add(cluster)
