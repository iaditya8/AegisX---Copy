import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.security_decision import (
    DecisionResponse,
    DecisionStatus,
    DecisionType,
)
from src.services.decision_type_registry import DecisionTypeRegistry
from src.services.decision_fingerprint_service import DecisionFingerprintService
from src.services.decision_history_service import DecisionHistoryService
from src.infrastructure.cache.cache_dict import CacheDict
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import (
    SecurityDecision as DBDecision,
    IntelligenceEvent,
)
from src.core.tenant import get_current_tenant_id


class SecurityDecisionService:
    # L2 caches
    _decisions = CacheDict("security_decision")
    _fingerprint_lookup = CacheDict("security_decision_fingerprints")

    @classmethod
    def clear_decisions(cls) -> None:
        """Clear all in-memory decisions and registry caches."""
        cls._decisions.clear()
        cls._fingerprint_lookup.clear()
        DecisionHistoryService.clear_history()

    @classmethod
    async def bootstrap(cls, db: AsyncSession) -> None:
        """Bootstrap the L2 cache from PostgreSQL database."""
        cls.clear_decisions()
        async with UnitOfWork() as uow:
            db_decisions = await uow.decision_repo.list()
            for db_d in db_decisions:
                decision = DecisionResponse(
                    decision_id=db_d.id,
                    decision_fingerprint=db_d.decision_fingerprint,
                    decision_type=DecisionType(db_d.decision_type),
                    target_entity_id=db_d.target_entity_id,
                    option_name=db_d.option_name,
                    status=DecisionStatus(db_d.status),
                    scope_id=db_d.scope_id,
                    created_at=db_d.created_at,
                    updated_at=db_d.updated_at,
                    tradeoff_matrix=db_d.tradeoff_matrix,
                    impact_metrics=db_d.impact_metrics,
                )
                cls._decisions[db_d.id] = decision
                cls._fingerprint_lookup[db_d.decision_fingerprint] = db_d.id

    @classmethod
    def get_all_decisions(cls) -> List[DecisionResponse]:
        """Retrieve all decisions currently tracked."""
        return list(cls._decisions.values())

    @classmethod
    def get_decision(cls, decision_id: uuid.UUID) -> Optional[DecisionResponse]:
        """Retrieve a specific decision by ID."""
        return cls._decisions.get(decision_id)

    @classmethod
    def get_decision_by_fingerprint(cls, fingerprint: str) -> Optional[DecisionResponse]:
        """Retrieve a decision by fingerprint."""
        did = cls._fingerprint_lookup.get(fingerprint)
        if did:
            return cls.get_decision(did)
        return None

    @classmethod
    async def get_decision_by_fingerprint_db(cls, fingerprint: str, uow: Optional[UnitOfWork] = None) -> Optional[DecisionResponse]:
        """Retrieve a decision by fingerprint from database."""
        from sqlalchemy import select
        async def _get(uow_inst: UnitOfWork) -> Optional[DecisionResponse]:
            stmt = select(DBDecision).filter_by(decision_fingerprint=fingerprint)
            res = await uow_inst.session.execute(stmt)
            db_d = res.scalar_one_or_none()
            if db_d:
                return DecisionResponse(
                    decision_id=db_d.id,
                    decision_fingerprint=db_d.decision_fingerprint,
                    decision_type=DecisionType(db_d.decision_type),
                    target_entity_id=db_d.target_entity_id,
                    option_name=db_d.option_name,
                    status=DecisionStatus(db_d.status),
                    scope_id=db_d.scope_id,
                    created_at=db_d.created_at,
                    updated_at=db_d.updated_at,
                    tradeoff_matrix=db_d.tradeoff_matrix,
                    impact_metrics=db_d.impact_metrics,
                )
            return None

        if uow:
            return await _get(uow)
        else:
            async with UnitOfWork() as uow_new:
                return await _get(uow_new)

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
    async def create_or_sync_decision(
        cls,
        decision_type: DecisionType,
        target_entity_id: uuid.UUID,
        option_name: str,
        scope_id: Optional[uuid.UUID] = None,
    ) -> DecisionResponse:
        """Create or synchronize a security decision option enforcing terminal state protection."""
        type_str = decision_type.value if hasattr(decision_type, "value") else str(decision_type)
        if not DecisionTypeRegistry.validate(type_str):
            raise ValueError(f"Invalid Decision Type: {decision_type}")

        decision_type_enum = DecisionType(type_str)
        fingerprint = DecisionFingerprintService.generate_fingerprint(
            decision_type_enum, target_entity_id, option_name
        )

        existing = cls.get_decision_by_fingerprint(fingerprint)
        if not existing:
            existing = await cls.get_decision_by_fingerprint_db(fingerprint)
            if existing:
                cls._decisions[existing.decision_id] = existing
                cls._fingerprint_lookup[fingerprint] = existing.decision_id

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        if existing:
            if existing.status == DecisionStatus.ARCHIVED:
                return existing
            return existing

        decision_id = uuid.uuid4()
        decision = DecisionResponse(
            decision_id=decision_id,
            decision_fingerprint=fingerprint,
            decision_type=decision_type_enum,
            target_entity_id=target_entity_id,
            option_name=option_name,
            status=DecisionStatus.ACTIVE,
            scope_id=cls._get_uuid(scope_id),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            tradeoff_matrix=None,
            impact_metrics=None,
        )

        cls._decisions[decision_id] = decision
        cls._fingerprint_lookup[fingerprint] = decision_id

        async with UnitOfWork() as uow:
            db_d = DBDecision(
                tenant_id=tenant_id,
                id=decision_id,
                decision_fingerprint=fingerprint,
                decision_type=decision_type_enum.value,
                target_entity_id=target_entity_id,
                option_name=option_name,
                status=DecisionStatus.ACTIVE.value,
                scope_id=decision.scope_id,
                tradeoff_matrix=None,
                impact_metrics=None,
            )
            await uow.decision_repo.save(db_d)
            await uow.session.flush()
            await DecisionHistoryService.record_event(
                decision_id, "CREATED", f"Created decision recommendation: {option_name}", uow=uow
            )
            # Stage outbox event
            outbox_evt = IntelligenceEvent(
                tenant_id=tenant_id,
                event_type="decision.created",
                payload={
                    "decision_id": str(decision_id),
                    "status": DecisionStatus.ACTIVE.value,
                }
            )
            uow.session.add(outbox_evt)
            await uow.commit()

        return decision

    @classmethod
    async def recommend_decision(cls, decision_id: uuid.UUID) -> DecisionResponse:
        """Transition decision to RECOMMENDED status."""
        decision = cls.get_decision(decision_id)
        if not decision:
            raise ValueError(f"Decision with ID {decision_id} not found")

        if decision.status == DecisionStatus.ARCHIVED:
            return decision

        if decision.status != DecisionStatus.RECOMMENDED:
            decision.status = DecisionStatus.RECOMMENDED
            decision.updated_at = datetime.now(timezone.utc)
            tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
            async with UnitOfWork() as uow:
                db_d = await uow.decision_repo.get(decision_id)
                if db_d:
                    db_d.status = DecisionStatus.RECOMMENDED.value
                    db_d.updated_at = decision.updated_at
                    await DecisionHistoryService.record_event(
                        decision_id, "RECOMMENDED", "Decision option status changed to RECOMMENDED", uow=uow
                    )
                    # Stage outbox event
                    outbox_evt = IntelligenceEvent(
                        tenant_id=tenant_id,
                        event_type="decision.recommended",
                        payload={
                            "decision_id": str(decision_id),
                            "status": DecisionStatus.RECOMMENDED.value,
                        }
                    )
                    uow.session.add(outbox_evt)
                    await uow.commit()

        return decision

    @classmethod
    async def commit_decision(cls, decision_id: uuid.UUID) -> DecisionResponse:
        """Transition decision to COMMITTED status."""
        decision = cls.get_decision(decision_id)
        if not decision:
            raise ValueError(f"Decision with ID {decision_id} not found")

        if decision.status == DecisionStatus.ARCHIVED:
            return decision

        if decision.status != DecisionStatus.COMMITTED:
            decision.status = DecisionStatus.COMMITTED
            decision.updated_at = datetime.now(timezone.utc)
            tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
            async with UnitOfWork() as uow:
                db_d = await uow.decision_repo.get(decision_id)
                if db_d:
                    db_d.status = DecisionStatus.COMMITTED.value
                    db_d.updated_at = decision.updated_at
                    await DecisionHistoryService.record_event(
                        decision_id, "COMMITTED", "Decision option status changed to COMMITTED", uow=uow
                    )
                    # Stage outbox event
                    outbox_evt = IntelligenceEvent(
                        tenant_id=tenant_id,
                        event_type="decision.committed",
                        payload={
                            "decision_id": str(decision_id),
                            "status": DecisionStatus.COMMITTED.value,
                        }
                    )
                    uow.session.add(outbox_evt)
                    await uow.commit()

        return decision

    @classmethod
    async def archive_decision(cls, decision_id: uuid.UUID) -> DecisionResponse:
        """Transition decision to ARCHIVED status."""
        decision = cls.get_decision(decision_id)
        if not decision:
            raise ValueError(f"Decision with ID {decision_id} not found")

        if decision.status != DecisionStatus.ARCHIVED:
            decision.status = DecisionStatus.ARCHIVED
            decision.updated_at = datetime.now(timezone.utc)
            tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
            async with UnitOfWork() as uow:
                db_d = await uow.decision_repo.get(decision_id)
                if db_d:
                    db_d.status = DecisionStatus.ARCHIVED.value
                    db_d.updated_at = decision.updated_at
                    await DecisionHistoryService.record_event(
                        decision_id, "ARCHIVED", "Decision option status changed to ARCHIVED", uow=uow
                    )
                    # Stage outbox event
                    outbox_evt = IntelligenceEvent(
                        tenant_id=tenant_id,
                        event_type="decision.archived",
                        payload={
                            "decision_id": str(decision_id),
                            "status": DecisionStatus.ARCHIVED.value,
                        }
                    )
                    uow.session.add(outbox_evt)
                    await uow.commit()

        return decision

    @classmethod
    async def sync_decision_recommendations(cls, db=None) -> None:
        """Query GRC assessments and other active domains to sync decision recommendations."""
        # 1. GRC Assessments
        from src.services.governance_risk_compliance_service import GovernanceRiskComplianceService
        assessments = await GovernanceRiskComplianceService.get_all_assessments()
        for assess in assessments:
            if isinstance(assess, dict):
                fw_type = assess.get("framework_type") or assess.get("framework_name") or "Framework"
                target_id = assess.get("assessment_id")
                scope_id = assess.get("scope_id")
            else:
                fw_val = getattr(assess, "framework_type", None)
                if fw_val and hasattr(fw_val, "value"):
                    fw_type = fw_val.value
                elif fw_val:
                    fw_type = str(fw_val)
                else:
                    fw_type = "Framework"
                target_id = assess.assessment_id
                scope_id = assess.scope_id

            fw_formatted = fw_type.replace("_", " ")
            option_name = f"Implement Control: {fw_formatted}"

            await cls.create_or_sync_decision(
                decision_type=DecisionType.COMPLIANCE_CONTROL,
                target_entity_id=target_id,
                option_name=option_name,
                scope_id=scope_id,
            )

        # 2. Remediations
        from src.services.remediation_service import RemediationService
        for rem in RemediationService.get_all_remediations():
            scope_id = None
            if db:
                try:
                    from src.infrastructure.database.models import Asset
                    asset = await db.get(Asset, rem.asset_id)
                    if asset:
                        scope_id = asset.scope_id
                except Exception:
                    pass
            await cls.create_or_sync_decision(
                decision_type=DecisionType.REMEDIATION,
                target_entity_id=rem.remediation_id,
                option_name=f"Remediate Vulnerability: {rem.remediation_id}",
                scope_id=scope_id,
            )
