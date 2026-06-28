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
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)


class ThreatIntelligenceService:
    # in-memory store: threat_intel_id -> ThreatRecord
    _threats: Dict[uuid.UUID, ThreatRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

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
        """Clear all GRC threat intelligence records and lookup cache."""
        cls._threats.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_threats(cls) -> List[ThreatRecord]:
        """Retrieve all GRC threat intelligence records."""
        return list(cls._threats.values())

    @classmethod
    def get_threat(cls, threat_intel_id: uuid.UUID) -> Optional[ThreatRecord]:
        """Retrieve a GRC threat intelligence record by ID."""
        return cls._threats.get(threat_intel_id)

    @classmethod
    def get_threat_by_fingerprint(cls, fingerprint: str) -> Optional[ThreatRecord]:
        """Retrieve a GRC threat intelligence record by fingerprint."""
        threat_intel_id = cls._fingerprint_lookup.get(fingerprint)
        if threat_intel_id:
            return cls.get_threat(threat_intel_id)
        return None

    @classmethod
    async def create_or_sync_threat(
        cls,
        value: str,
        indicator_type: ThreatIndicatorType,
        source: str,
        tags: List[str],
        scope_id: Optional[uuid.UUID] = None,
    ) -> ThreatRecord:
        """Create or synchronize GRC threat intelligence record enforcing identity rules."""
        fingerprint = ThreatIntelFingerprintService.generate_fingerprint(
            indicator_type.value, value, scope_id
        )
        existing = cls.get_threat_by_fingerprint(fingerprint)

        # Validate source
        if not ThreatSourceRegistry.validate(source):
            raise ValueError(f"Unsupported threat intelligence source '{source}'")

        # Validate indicator type
        if not ThreatIndicatorTypeRegistry.validate(indicator_type.value):
            raise ValueError(f"Unsupported threat indicator type '{indicator_type.value}'")

        # Calculate severity and initial fusion score
        initial_score = ThreatIntelFusionService.calculate_fusion_score(value, indicator_type.value)
        severity = ThreatSeverityRegistry.determine_severity(initial_score)

        if existing:
            if existing.status == ThreatIntelStatus.ARCHIVED:
                # Terminal State Rule
                return existing

            changed = False
            if existing.value != value:
                existing.value = value
                changed = True
            if existing.severity != severity:
                existing.severity = severity
                changed = True
                ThreatIntelHistoryEntry = ThreatIntelHistoryService.record_event(
                    existing.threat_intel_id, "UPDATED", f"Threat severity updated to {severity}"
                )

            # Sync tags (preserve existing but append new valid ones)
            for t in tags:
                if t not in existing.tags:
                    existing.tags.append(t)
                    changed = True

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
            return existing

        # Create new record
        threat_intel_id = uuid.uuid4()

        record = ThreatRecord(
            threat_intel_id=threat_intel_id,
            threat_intel_fingerprint=fingerprint,
            value=value,
            indicator_type=indicator_type,
            status=ThreatIntelStatus.ACTIVE,
            severity=severity,
            confidence=None,
            source=source,
            tags=tags,
            scope_id=scope_id,
        )

        cls._threats[threat_intel_id] = record
        cls._fingerprint_lookup[fingerprint] = threat_intel_id

        ThreatIntelHistoryService.record_event(
            threat_intel_id, "CREATED", f"Threat intelligence record created: '{value}'"
        )
        return record

    @classmethod
    async def sync_threats(cls, db: AsyncSession) -> List[ThreatRecord]:
        """Continuous sync loop GRC threat intelligence feeds."""
        synced = []

        # 1. IP indicator
        rec1 = await cls.create_or_sync_threat(
            value="192.168.1.100",
            indicator_type=ThreatIndicatorType.IP,
            source="OSINT",
            tags=["malware", "phishing"],
        )
        synced.append(rec1)

        # 2. Domain indicator
        rec2 = await cls.create_or_sync_threat(
            value="evil-domain.com",
            indicator_type=ThreatIndicatorType.DOMAIN,
            source="COMMERCIAL",
            tags=["ransomware", "lateral_movement"],
        )
        synced.append(rec2)

        return synced

    @classmethod
    def fuse_threat(cls, threat_intel_id: uuid.UUID, confidence: float) -> ThreatRecord:
        """Persist fused confidence score and transition status to FUSED (Finding 2)."""
        record = cls.get_threat(threat_intel_id)
        if not record:
            raise ValueError(f"Threat intelligence record {threat_intel_id} not found")

        # Terminal state protection
        if record.status == ThreatIntelStatus.ARCHIVED:
            return record

        changed = False
        old_confidence = record.confidence
        if old_confidence != confidence:
            record.confidence = float(confidence)
            changed = True
            ThreatIntelHistoryService.record_event(
                threat_intel_id, "FUSION_CONFIDENCE_UPDATED", f"Fusion confidence score updated from {old_confidence} to {confidence}"
            )

        if record.status != ThreatIntelStatus.FUSED:
            old_status = record.status
            record.status = ThreatIntelStatus.FUSED
            changed = True
            ThreatIntelHistoryService.record_event(
                threat_intel_id, "FUSED", f"Status transitioned from {old_status.value} to FUSED"
            )

        if changed:
            record.updated_at = datetime.now(timezone.utc)

        return record

    @classmethod
    def transition_status(
        cls, threat_intel_id: uuid.UUID, new_status: ThreatIntelStatus
    ) -> ThreatRecord:
        """Safely transition GRC threat intelligence status enforcing forward-only rules."""
        record = cls.get_threat(threat_intel_id)
        if not record:
            raise ValueError(f"Threat intelligence record {threat_intel_id} not found")

        if record.status == ThreatIntelStatus.ARCHIVED:
            if new_status != ThreatIntelStatus.ARCHIVED:
                raise ValueError("Cannot transition out of terminal ARCHIVED state")
            return record

        allowed = cls.ALLOWED_TRANSITIONS.get(record.status, set())
        if new_status not in allowed:
            raise ValueError(f"Invalid transition from {record.status.value} to {new_status.value}")

        old_status = record.status
        record.status = new_status
        record.updated_at = datetime.now(timezone.utc)

        event_map = {
            ThreatIntelStatus.IN_TRIAGE: "TRIAGED",
            ThreatIntelStatus.FUSED: "FUSED",
            ThreatIntelStatus.ARCHIVED: "ARCHIVED",
        }
        event_type = event_map.get(new_status, "STATUS_CHANGED")

        ThreatIntelHistoryService.record_event(
            threat_intel_id,
            event_type,
            f"Status transitioned from {old_status.value} to {new_status.value}",
        )
        return record

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
