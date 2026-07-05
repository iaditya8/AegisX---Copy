import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.tenant import get_current_tenant_id
from src.domain.entities.cyber_risk_quantification import (
    RiskQuantificationStatus,
    RiskScenarioType,
    CyberRiskResponse,
)
from src.infrastructure.database.models import CyberRiskRecord, CyberRiskScenario, CyberRiskForecast, CyberRiskHistory, IntelligenceEvent, AuditLog
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.services.risk_quantification_fingerprint_service import RiskQuantificationFingerprintService
from src.services.quantified_risk_history_service import QuantifiedRiskHistoryService
from src.services.risk_frequency_registry import RiskFrequencyRegistry
from src.services.risk_impact_registry import RiskImpactRegistry
from src.services.loss_expectancy_service import LossExpectancyService
from src.services.residual_risk_service import ResidualRiskService
from src.services.risk_trend_service import RiskTrendService
from src.infrastructure.cache.cache_dict import CacheDict


class CyberRiskQuantificationService:
    _risks = CacheDict("cyber_risk")
    _fingerprint_lookup = CacheDict("cyber_risk_fingerprints")

    ALLOWED_TRANSITIONS = {
        RiskQuantificationStatus.ACTIVE: {
            RiskQuantificationStatus.ACCEPTED,
            RiskQuantificationStatus.MITIGATED,
            RiskQuantificationStatus.CLOSED,
        },
        RiskQuantificationStatus.ACCEPTED: {RiskQuantificationStatus.CLOSED},
        RiskQuantificationStatus.MITIGATED: {RiskQuantificationStatus.CLOSED},
        RiskQuantificationStatus.CLOSED: set(),  # Terminal
    }

    @classmethod
    def clear_risks(cls) -> None:
        """Clear all risk records and lookup cache."""
        cls._risks.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    async def get_all_risks(cls) -> List[CyberRiskRecord]:
        """Retrieve all risk records."""
        async with UnitOfWork() as uow:
            tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
            records = await uow.risk_repo.get_active_risks(tenant_id)
            for r in records:
                cls._risks[r.id] = r
                cls._fingerprint_lookup[r.risk_fingerprint] = r.id
            return records

    @classmethod
    async def get_risk(cls, risk_id: uuid.UUID) -> Optional[CyberRiskRecord]:
        """Retrieve a risk record by ID."""
        cached = cls._risks.get(risk_id)
        if cached:
            return cached
        async with UnitOfWork() as uow:
            record = await uow.risk_repo.get(risk_id)
            if record and not record.is_deleted:
                cls._risks[record.id] = record
                cls._fingerprint_lookup[record.risk_fingerprint] = record.id
                return record
        return None

    @classmethod
    async def get_risk_by_fingerprint(cls, fingerprint: str) -> Optional[CyberRiskRecord]:
        """Retrieve a risk record by fingerprint."""
        risk_id = cls._fingerprint_lookup.get(fingerprint)
        if risk_id:
            cached = cls._risks.get(risk_id)
            if cached:
                return cached
        async with UnitOfWork() as uow:
            tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
            record = await uow.risk_repo.get_risk_by_fingerprint(tenant_id, fingerprint)
            if record:
                cls._risks[record.id] = record
                cls._fingerprint_lookup[record.risk_fingerprint] = record.id
                return record
        return None

    @classmethod
    async def create_or_sync_risk(
        cls,
        title: str,
        description: str,
        scenario_type: RiskScenarioType,
        frequency_label: str,
        impact_label: str,
        exposure_value: float,
        scope_id: Optional[uuid.UUID] = None,
        uow: Optional[UnitOfWork] = None,
    ) -> CyberRiskRecord:
        """Create or synchronize a quantified risk record based on identity rules."""
        fingerprint = RiskQuantificationFingerprintService.generate_fingerprint(
            scenario_type.value, title, scope_id
        )
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        aro = RiskFrequencyRegistry.get_aro(frequency_label)
        factor = RiskImpactRegistry.get_factor(impact_label)

        sle = LossExpectancyService.calculate_sle(exposure_value, factor)
        ale = LossExpectancyService.calculate_ale(sle, aro)

        inherent = ResidualRiskService.calculate_inherent_risk_score(exposure_value, factor, aro)
        mitigation_eff = 75.0  # standard effectiveness
        residual = ResidualRiskService.calculate_residual_risk_score(inherent, mitigation_eff)

        async def _sync(uow_inst: UnitOfWork) -> CyberRiskRecord:
            existing = await uow_inst.risk_repo.get_risk_by_fingerprint(tenant_id, fingerprint)
            if existing:
                if existing.status == RiskQuantificationStatus.CLOSED.value:
                    return existing

                changed = False
                if float(existing.exposure_value) != exposure_value:
                    existing.exposure_value = exposure_value
                    changed = True
                if float(existing.single_loss_expectancy) != sle:
                    existing.single_loss_expectancy = sle
                    changed = True
                if float(existing.annualized_loss_expectancy) != ale:
                    existing.annualized_loss_expectancy = ale
                    changed = True
                    hist = CyberRiskHistory(
                        risk_id=existing.id,
                        event_type="ALE_CHANGED",
                        details=f"Annualized Loss Expectancy updated to {ale}",
                        tenant_id=tenant_id
                    )
                    uow_inst.session.add(hist)
                if float(existing.inherent_risk_score) != inherent or float(existing.residual_risk_score) != residual:
                    existing.inherent_risk_score = inherent
                    existing.residual_risk_score = residual
                    changed = True
                    hist = CyberRiskHistory(
                        risk_id=existing.id,
                        event_type="RESIDUAL_RISK_CHANGED",
                        details=f"Residual risk score updated to {residual}",
                        tenant_id=tenant_id
                    )
                    uow_inst.session.add(hist)

                if changed:
                    existing.updated_at = datetime.now(timezone.utc)
                    existing.version += 1
                    
                    event = IntelligenceEvent(
                        tenant_id=tenant_id,
                        domain="risk",
                        entity_id=existing.id,
                        event_type="risk.updated",
                        payload={"id": str(existing.id), "title": existing.title, "residual_risk_score": float(existing.residual_risk_score)},
                        status="pending"
                    )
                    uow_inst.session.add(event)
                    
                    audit = AuditLog(
                        tenant_id=tenant_id,
                        actor_id=existing.created_by,
                        action="update_risk",
                        target_type="risk",
                        target_id=existing.id,
                        metadata_json={"title": existing.title},
                        timestamp=datetime.now(timezone.utc)
                    )
                    uow_inst.session.add(audit)

                return existing

            record = CyberRiskRecord(
                risk_fingerprint=fingerprint,
                scenario_type=scenario_type.value,
                title=title,
                description=description,
                exposure_value=exposure_value,
                single_loss_expectancy=sle,
                annualized_loss_expectancy=ale,
                inherent_risk_score=inherent,
                residual_risk_score=residual,
                mitigation_effectiveness=mitigation_eff,
                status=RiskQuantificationStatus.ACTIVE.value,
                scope_id=scope_id,
                tenant_id=tenant_id,
                version=1
            )
            await uow_inst.risk_repo.save(record)
            await uow_inst.session.flush()

            hist = CyberRiskHistory(
                risk_id=record.id,
                event_type="CREATED",
                details=f"Quantified risk record created: '{title}'",
                tenant_id=tenant_id
            )
            uow_inst.session.add(hist)

            event = IntelligenceEvent(
                tenant_id=tenant_id,
                domain="risk",
                entity_id=record.id,
                event_type="risk.created",
                payload={"id": str(record.id), "title": record.title, "residual_risk_score": float(record.residual_risk_score)},
                status="pending"
            )
            uow_inst.session.add(event)

            audit = AuditLog(
                tenant_id=tenant_id,
                actor_id=None,
                action="create_risk",
                target_type="risk",
                target_id=record.id,
                metadata_json={"title": record.title},
                timestamp=datetime.now(timezone.utc)
            )
            uow_inst.session.add(audit)

            RiskTrendService.calculate_trends(record.id, exposure_value)
            return record

        if uow:
            rec = await _sync(uow)
            cls._risks[rec.id] = rec
            cls._fingerprint_lookup[rec.risk_fingerprint] = rec.id
            return rec
        else:
            async with UnitOfWork() as new_uow:
                rec = await _sync(new_uow)
                await new_uow.commit()
                cls._risks[rec.id] = rec
                cls._fingerprint_lookup[rec.risk_fingerprint] = rec.id
                return rec

    @classmethod
    async def sync_risks(cls, db: AsyncSession) -> List[CyberRiskRecord]:
        """Continuous sync loop discovering cyber risks posture."""
        synced = []
        async with UnitOfWork() as uow:
            rec1 = await cls.create_or_sync_risk(
                title="Cloud S3 Bucket Leaks",
                description="Exposes sensitive corporate backups.",
                scenario_type=RiskScenarioType.CLOUD_COMPROMISE,
                frequency_label="OCCASIONAL",
                impact_label="HIGH",
                exposure_value=120000.0,
                uow=uow
            )
            synced.append(rec1)

            rec2 = await cls.create_or_sync_risk(
                title="Ransomware Hostage Crypt",
                description="Cryptolocker infection on local servers.",
                scenario_type=RiskScenarioType.RANSOMWARE,
                frequency_label="RARE",
                impact_label="CRITICAL",
                exposure_value=250000.0,
                uow=uow
            )
            synced.append(rec2)
            await uow.commit()

        for r in synced:
            cls._risks[r.id] = r
            cls._fingerprint_lookup[r.risk_fingerprint] = r.id

        return synced

    @classmethod
    async def transition_status(
        cls, risk_id: uuid.UUID, new_status: RiskQuantificationStatus
    ) -> CyberRiskRecord:
        """Safely transition report status enforcing forward-only rules and terminal states."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            record = await uow.risk_repo.get(risk_id)
            if not record or record.is_deleted:
                raise ValueError(f"Risk record {risk_id} not found")

            current_status_enum = RiskQuantificationStatus(record.status)
            if current_status_enum == RiskQuantificationStatus.CLOSED:
                return record

            allowed = cls.ALLOWED_TRANSITIONS.get(current_status_enum, set())
            if new_status not in allowed:
                raise ValueError(f"Invalid transition from {record.status} to {new_status.value}")

            old_status = record.status
            record.status = new_status.value
            record.updated_at = datetime.now(timezone.utc)
            record.version += 1

            event_map = {
                RiskQuantificationStatus.ACCEPTED: "ACCEPTED",
                RiskQuantificationStatus.MITIGATED: "MITIGATED",
                RiskQuantificationStatus.CLOSED: "CLOSED",
            }
            event_type = event_map.get(new_status, "STATUS_CHANGED")

            hist = CyberRiskHistory(
                risk_id=record.id,
                event_type=event_type,
                details=f"Status transitioned from {old_status} to {new_status.value}",
                tenant_id=tenant_id
            )
            uow.session.add(hist)

            event = IntelligenceEvent(
                tenant_id=tenant_id,
                domain="risk",
                entity_id=record.id,
                event_type="risk.updated" if new_status != RiskQuantificationStatus.CLOSED else "risk.archived",
                payload={"id": str(record.id), "status": record.status},
                status="pending"
            )
            uow.session.add(event)

            audit = AuditLog(
                tenant_id=tenant_id,
                actor_id=record.created_by,
                action="transition_risk",
                target_type="risk",
                target_id=record.id,
                metadata_json={"old_status": old_status, "new_status": record.status},
                timestamp=datetime.now(timezone.utc)
            )
            uow.session.add(audit)

            await uow.commit()

            cls._risks[record.id] = record
            cls._fingerprint_lookup[record.risk_fingerprint] = record.id
            return record

    @classmethod
    def to_response(cls, record: CyberRiskRecord) -> CyberRiskResponse:
        return CyberRiskResponse(
            risk_id=record.id,
            risk_fingerprint=record.risk_fingerprint,
            scenario_type=RiskScenarioType(record.scenario_type),
            title=record.title,
            description=record.description,
            exposure_value=float(record.exposure_value),
            single_loss_expectancy=float(record.single_loss_expectancy),
            annualized_loss_expectancy=float(record.annualized_loss_expectancy),
            inherent_risk_score=float(record.inherent_risk_score),
            residual_risk_score=float(record.residual_risk_score),
            mitigation_effectiveness=float(record.mitigation_effectiveness),
            status=RiskQuantificationStatus(record.status),
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
