import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.threat_intel import (
    ThreatIntelStatus,
    ThreatSeverity,
    ThreatIndicatorType,
    ThreatIntelRecordResponse,
)
from src.services.threat_intel_fingerprint_service import ThreatIntelFingerprintService
from src.services.threat_intel_history_service import ThreatIntelHistoryService
from src.services.threat_intel_fusion_service import ThreatIntelFusionService
from src.services.threat_source_registry import ThreatSourceRegistry
from src.services.threat_indicator_type_registry import ThreatIndicatorTypeRegistry
from src.services.threat_severity_registry import ThreatSeverityRegistry


from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import ThreatIntelIOC, IntelligenceEvent
from src.core.tenant import get_current_tenant_id, require_current_tenant_id
from src.infrastructure.cache.cache_dict import CacheDict


class ThreatRecord:
    def __init__(
        self,
        threat_intel_id: uuid.UUID,
        threat_intel_fingerprint: str,
        value: str,
        indicator_type: ThreatIndicatorType,
        status: ThreatIntelStatus,
        severity: ThreatSeverity,
        source: str,
        tags: List[str],
        confidence: Optional[float] = None,
        scope_id: Optional[uuid.UUID] = None,
        tenant_id: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.threat_intel_id = threat_intel_id
        self.threat_intel_fingerprint = threat_intel_fingerprint
        self.value = value
        self.indicator_type = indicator_type
        self.status = status
        self.severity = severity
        self.confidence = confidence
        self.source = source
        self.tags = tags
        self.scope_id = scope_id
        self.tenant_id = tenant_id or require_current_tenant_id()
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)


class ThreatIntelligenceService:
    # L2 caches
    _threats = CacheDict("grc_threat")
    _fingerprint_lookup = CacheDict("grc_threat_fingerprints")

    ALLOWED_TRANSITIONS = {
        ThreatIntelStatus.ACTIVE: {
            ThreatIntelStatus.IN_TRIAGE,
            ThreatIntelStatus.FUSED,
            ThreatIntelStatus.ARCHIVED,
        },
        ThreatIntelStatus.IN_TRIAGE: {
            ThreatIntelStatus.FUSED,
            ThreatIntelStatus.ARCHIVED,
        },
        ThreatIntelStatus.FUSED: {ThreatIntelStatus.ARCHIVED},
        ThreatIntelStatus.ARCHIVED: set(),  # Terminal
    }

    @classmethod
    def clear_threats(cls) -> None:
        """Clear L2 cache."""
        cls._threats.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_threats(cls) -> List[ThreatRecord]:
        """Retrieve all GRC threat intelligence records (L2 cache tenant filtered)."""
        tenant_id = require_current_tenant_id()
        return [r for r in cls._threats.values() if r.tenant_id == tenant_id]

    @classmethod
    def get_threat(cls, threat_intel_id: uuid.UUID) -> Optional[ThreatRecord]:
        """Retrieve a GRC threat intelligence record by ID (L2 cache check)."""
        tenant_id = require_current_tenant_id()
        cached = cls._threats.get(threat_intel_id)
        if cached and cached.tenant_id == tenant_id:
            return cached
        return None

    @classmethod
    def get_threat_by_fingerprint(cls, fingerprint: str) -> Optional[ThreatRecord]:
        """Retrieve a GRC threat intelligence record by fingerprint (L2 cache check)."""
        tenant_id = require_current_tenant_id()
        threat_intel_id = cls._fingerprint_lookup.get(fingerprint)
        if threat_intel_id:
            cached = cls.get_threat(threat_intel_id)
            if cached and cached.tenant_id == tenant_id:
                return cached
        return None

    @classmethod
    def _db_to_record(cls, db_ioc: ThreatIntelIOC) -> ThreatRecord:
        return ThreatRecord(
            threat_intel_id=db_ioc.ioc_id,
            threat_intel_fingerprint=db_ioc.ioc_fingerprint,
            value=db_ioc.value,
            indicator_type=ThreatIndicatorType(db_ioc.ioc_type),
            status=ThreatIntelStatus(db_ioc.status),
            severity=ThreatSeverity(db_ioc.severity),
            confidence=db_ioc.confidence,
            source=db_ioc.feed_type,
            tags=db_ioc.tags,
            scope_id=db_ioc.scope_id,
            tenant_id=db_ioc.tenant_id,
            created_at=db_ioc.created_at,
            updated_at=db_ioc.updated_at,
        )

    @classmethod
    async def create_or_sync_threat(
        cls,
        value: str,
        indicator_type: ThreatIndicatorType,
        source: str,
        tags: List[str],
        scope_id: Optional[uuid.UUID] = None,
        uow: Optional[UnitOfWork] = None,
    ) -> ThreatRecord:
        """Create or synchronize GRC threat intelligence record enforcing identity rules."""
        tenant_id = require_current_tenant_id()
        fingerprint = ThreatIntelFingerprintService.generate_fingerprint(
            indicator_type.value if hasattr(indicator_type, "value") else indicator_type,
            value,
            scope_id
        )

        # Validate source
        if not ThreatSourceRegistry.validate(source):
            raise ValueError(f"Unsupported threat intelligence source '{source}'")

        # Validate indicator type
        indicator_type_val = indicator_type.value if hasattr(indicator_type, "value") else indicator_type
        if not ThreatIndicatorTypeRegistry.validate(indicator_type_val):
            raise ValueError(f"Unsupported threat indicator type '{indicator_type_val}'")

        # Calculate severity and initial fusion score
        initial_score = ThreatIntelFusionService.calculate_fusion_score(value, indicator_type_val)
        severity = ThreatSeverityRegistry.determine_severity(initial_score)

        async def _sync(uow_inst: UnitOfWork) -> ThreatIntelIOC:
            existing = await uow_inst.threat_repo.get_by_fingerprint(fingerprint)
            if existing:
                if existing.status == ThreatIntelStatus.ARCHIVED.value:
                    return existing

                changed = False
                if existing.value != value:
                    existing.value = value
                    changed = True

                severity_str = severity.value if hasattr(severity, "value") else severity
                if existing.severity != severity_str:
                    existing.severity = severity_str
                    changed = True
                    await ThreatIntelHistoryService.record_event(
                        existing.ioc_id, "UPDATED", f"Threat severity updated to {severity_str}", uow=uow_inst
                    )

                if existing.tags is None:
                    existing.tags = []
                for t in tags:
                    if t not in existing.tags:
                        existing.tags.append(t)
                        changed = True

                if changed:
                    existing.updated_at = datetime.now(timezone.utc)
                    # Stage event
                    event = IntelligenceEvent(
                        tenant_id=tenant_id,
                        domain="threat",
                        entity_id=existing.ioc_id,
                        event_type="threat.updated",
                        payload={"ioc_id": str(existing.ioc_id), "value": value},
                        status="pending"
                    )
                    uow_inst.session.add(event)
                return existing

            # Create new record
            ioc_id = uuid.uuid4()
            severity_str = severity.value if hasattr(severity, "value") else severity
            status_str = ThreatIntelStatus.ACTIVE.value
            indicator_type_str = indicator_type.value if hasattr(indicator_type, "value") else indicator_type
            db_record = ThreatIntelIOC(
                ioc_id=ioc_id,
                ioc_fingerprint=fingerprint,
                value=value,
                ioc_type=indicator_type_str,
                severity=severity_str,
                status=status_str,
                reputation=0,
                feed_type=source,
                confidence=None,
                tags=tags,
                scope_id=scope_id,
                tenant_id=tenant_id,
                version=1
            )
            await uow_inst.threat_repo.save(db_record)
            await uow_inst.session.flush()

            await ThreatIntelHistoryService.record_event(
                ioc_id, "CREATED", f"Threat intelligence record created: '{value}'", uow=uow_inst
            )

            # Stage outbox event
            event = IntelligenceEvent(
                tenant_id=tenant_id,
                domain="threat",
                entity_id=ioc_id,
                event_type="threat.created",
                payload={"ioc_id": str(ioc_id), "value": value},
                status="pending"
            )
            uow_inst.session.add(event)
            return db_record

        if uow:
            db_ioc = await _sync(uow)
        else:
            async with UnitOfWork() as new_uow:
                db_ioc = await _sync(new_uow)
                await new_uow.commit()

        # Warm L2 cache
        record = cls._db_to_record(db_ioc)
        cls._threats[db_ioc.ioc_id] = record
        cls._fingerprint_lookup[db_ioc.ioc_fingerprint] = db_ioc.ioc_id

        return record

    @classmethod
    async def sync_threats(cls, db: AsyncSession) -> List[ThreatRecord]:
        """Continuous sync loop GRC threat intelligence feeds."""
        synced = []
        async with UnitOfWork() as uow:
            # 1. IP indicator
            rec1 = await cls.create_or_sync_threat(
                value="192.168.1.100",
                indicator_type=ThreatIndicatorType.IP,
                source="OSINT",
                tags=["malware", "phishing"],
                uow=uow
            )
            synced.append(rec1)

            # 2. Domain indicator
            rec2 = await cls.create_or_sync_threat(
                value="evil-domain.com",
                indicator_type=ThreatIndicatorType.DOMAIN,
                source="COMMERCIAL",
                tags=["ransomware", "lateral_movement"],
                uow=uow
            )
            synced.append(rec2)
            await uow.commit()

        for r in synced:
            cls._threats[r.threat_intel_id] = r
            cls._fingerprint_lookup[r.threat_intel_fingerprint] = r.threat_intel_id

        return synced

    @classmethod
    async def fuse_threat(cls, threat_intel_id: uuid.UUID, confidence: float) -> ThreatRecord:
        """Persist fused confidence score and transition status to FUSED."""
        tenant_id = require_current_tenant_id()
        async with UnitOfWork() as uow:
            record = await uow.threat_repo.get(threat_intel_id)
            if not record:
                raise ValueError(f"Threat intelligence record {threat_intel_id} not found")

            if record.status == ThreatIntelStatus.ARCHIVED.value:
                return cls._db_to_record(record)

            changed = False
            old_confidence = record.confidence
            if old_confidence != confidence:
                record.confidence = float(confidence)
                changed = True
                await ThreatIntelHistoryService.record_event(
                    threat_intel_id,
                    "FUSION_CONFIDENCE_UPDATED",
                    f"Fusion confidence score updated from {old_confidence} to {confidence}",
                    uow=uow
                )

            if record.status != ThreatIntelStatus.FUSED.value:
                old_status = record.status
                record.status = ThreatIntelStatus.FUSED.value
                changed = True
                await ThreatIntelHistoryService.record_event(
                    threat_intel_id,
                    "FUSED",
                    f"Status transitioned from {old_status} to FUSED",
                    uow=uow
                )

            if changed:
                record.updated_at = datetime.now(timezone.utc)
                event = IntelligenceEvent(
                    tenant_id=tenant_id,
                    domain="threat",
                    entity_id=threat_intel_id,
                    event_type="threat.fused",
                    payload={"ioc_id": str(threat_intel_id), "confidence": confidence},
                    status="pending"
                )
                uow.session.add(event)
                await uow.commit()

            # Warm L2 cache
            record_res = cls._db_to_record(record)
            cls._threats[record.ioc_id] = record_res
            cls._fingerprint_lookup[record.ioc_fingerprint] = record.ioc_id

            return record_res

    @classmethod
    async def transition_status(
        cls, threat_intel_id: uuid.UUID, new_status: ThreatIntelStatus
    ) -> ThreatRecord:
        """Safely transition GRC threat intelligence status enforcing forward-only rules."""
        tenant_id = require_current_tenant_id()
        async with UnitOfWork() as uow:
            record = await uow.threat_repo.get(threat_intel_id)
            if not record:
                raise ValueError(f"Threat intelligence record {threat_intel_id} not found")

            current_status_enum = ThreatIntelStatus(record.status)
            if current_status_enum == ThreatIntelStatus.ARCHIVED:
                if new_status != ThreatIntelStatus.ARCHIVED:
                    raise ValueError("Cannot transition out of terminal ARCHIVED state")
                return cls._db_to_record(record)

            allowed = cls.ALLOWED_TRANSITIONS.get(current_status_enum, set())
            if new_status not in allowed:
                raise ValueError(f"Invalid transition from {record.status} to {new_status.value}")

            old_status = record.status
            record.status = new_status.value
            record.updated_at = datetime.now(timezone.utc)

            event_map = {
                ThreatIntelStatus.IN_TRIAGE: "TRIAGED",
                ThreatIntelStatus.FUSED: "FUSED",
                ThreatIntelStatus.ARCHIVED: "ARCHIVED",
            }
            event_type = event_map.get(new_status, "STATUS_CHANGED")

            await ThreatIntelHistoryService.record_event(
                threat_intel_id,
                event_type,
                f"Status transitioned from {old_status} to {new_status.value}",
                uow=uow
            )

            outbox_event_type = "threat.deleted" if new_status == ThreatIntelStatus.ARCHIVED else "threat.updated"
            event = IntelligenceEvent(
                tenant_id=tenant_id,
                domain="threat",
                entity_id=threat_intel_id,
                event_type=outbox_event_type,
                payload={"ioc_id": str(threat_intel_id), "status": new_status.value},
                status="pending"
            )
            uow.session.add(event)
            await uow.commit()

            # Warm L2 cache
            record_res = cls._db_to_record(record)
            cls._threats[record.ioc_id] = record_res
            cls._fingerprint_lookup[record.ioc_fingerprint] = record.ioc_id

            return record_res

    @classmethod
    def to_response(cls, record: ThreatRecord) -> ThreatIntelRecordResponse:
        return ThreatIntelRecordResponse(
            threat_intel_id=record.threat_intel_id,
            threat_intel_fingerprint=record.threat_intel_fingerprint,
            value=record.value,
            indicator_type=record.indicator_type,
            status=record.status,
            severity=record.severity,
            confidence=record.confidence,
            source=record.source,
            tags=record.tags,
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
