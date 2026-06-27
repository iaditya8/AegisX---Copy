import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.domain.entities.threat_intelligence import IOCSeverity, IOCStatus, IOCType, ThreatFeedType
from src.services.ioc_fingerprint_service import IOCFingerprintService
from src.services.ioc_history_service import IOCHistoryService
from src.services.ioc_type_registry import IOCTypeRegistry


class IOCRecord:
    def __init__(
        self,
        ioc_id: uuid.UUID,
        ioc_fingerprint: str,
        value: str,
        ioc_type: IOCType,
        severity: IOCSeverity,
        status: IOCStatus,
        reputation: int,
        feed_type: ThreatFeedType,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        scope_id: Optional[uuid.UUID] = None,
        threat_actors: Optional[List[str]] = None,
        campaigns: Optional[List[str]] = None,
    ):
        self.ioc_id = ioc_id
        self.ioc_fingerprint = ioc_fingerprint
        self.value = value
        self.ioc_type = ioc_type
        self.severity = severity
        self.status = status
        self.reputation = reputation
        self.feed_type = feed_type
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
        self.scope_id = scope_id
        self.threat_actors = threat_actors or []
        self.campaigns = campaigns or []


class IOCService:
    # in-memory store: ioc_id -> IOCRecord
    _iocs: Dict[uuid.UUID, IOCRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def clear_iocs(cls) -> None:
        """Clear all in-memory IOC records and references."""
        cls._iocs.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_iocs(cls) -> List[IOCRecord]:
        """Retrieve all IOCs."""
        return list(cls._iocs.values())

    @classmethod
    def get_ioc(cls, ioc_id: uuid.UUID) -> Optional[IOCRecord]:
        """Retrieve an IOC by ID."""
        return cls._iocs.get(ioc_id)

    @classmethod
    def get_ioc_by_fingerprint(cls, fingerprint: str) -> Optional[IOCRecord]:
        """Retrieve an IOC by its fingerprint."""
        ioc_id = cls._fingerprint_lookup.get(fingerprint)
        if ioc_id:
            return cls.get_ioc(ioc_id)
        return None

    @classmethod
    def create_or_sync_ioc(
        cls,
        value: str,
        ioc_type: IOCType,
        severity: IOCSeverity,
        reputation: int,
        feed_type: ThreatFeedType,
        scope_id: Optional[uuid.UUID] = None,
        threat_actors: Optional[List[str]] = None,
        campaigns: Optional[List[str]] = None,
    ) -> IOCRecord:
        """Create or synchronize an IOC record, keeping its identity and terminal states stable."""
        if not IOCTypeRegistry.validate_value(ioc_type, value):
            raise ValueError(f"Invalid IOC value format for type {ioc_type.value}: {value}")

        normalized = IOCTypeRegistry.normalize_value(ioc_type, value)
        fingerprint = IOCFingerprintService.generate_fingerprint(ioc_type, normalized)

        existing = cls.get_ioc_by_fingerprint(fingerprint)
        if existing:
            # Sync rules: preserve ioc_id, fingerprint, history, created_at, and terminal state
            changed = False

            # Check reputation changes
            if existing.reputation != reputation:
                old_rep = existing.reputation
                existing.reputation = reputation
                changed = True
                IOCHistoryService.record_event(
                    existing.ioc_id,
                    "REPUTATION_CHANGED",
                    f"Reputation score updated from {old_rep} to {reputation}",
                )

            # Metadata updates
            if existing.severity != severity:
                existing.severity = severity
                changed = True
            if existing.scope_id != scope_id:
                existing.scope_id = scope_id
                changed = True

            # Attribution updates
            new_actors = sorted(threat_actors or [])
            old_actors = sorted(existing.threat_actors)
            if old_actors != new_actors:
                existing.threat_actors = new_actors
                changed = True
                IOCHistoryService.record_event(
                    existing.ioc_id,
                    "ATTRIBUTION_CHANGED",
                    f"Threat actors updated to: {', '.join(new_actors)}",
                )

            new_camps = sorted(campaigns or [])
            old_camps = sorted(existing.campaigns)
            if old_camps != new_camps:
                existing.campaigns = new_camps
                changed = True
                IOCHistoryService.record_event(
                    existing.ioc_id,
                    "ATTRIBUTION_CHANGED",
                    f"Campaigns updated to: {', '.join(new_camps)}",
                )

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
                IOCHistoryService.record_event(
                    existing.ioc_id,
                    "UPDATED",
                    f"Updated metadata: severity={existing.severity.value}, status={existing.status.value}",
                )
            return existing

        # Create new active IOC
        ioc_id = uuid.uuid4()
        record = IOCRecord(
            ioc_id=ioc_id,
            ioc_fingerprint=fingerprint,
            value=normalized,
            ioc_type=ioc_type,
            severity=severity,
            status=IOCStatus.ACTIVE,
            reputation=reputation,
            feed_type=feed_type,
            scope_id=scope_id,
            threat_actors=threat_actors,
            campaigns=campaigns,
        )
        cls._iocs[ioc_id] = record
        cls._fingerprint_lookup[fingerprint] = ioc_id

        IOCHistoryService.record_event(
            ioc_id,
            "CREATED",
            f"Created active IOC record: {normalized} ({ioc_type.value})",
        )
        return record

    @classmethod
    def expire_ioc(cls, ioc_id: uuid.UUID) -> IOCRecord:
        """Mark an IOC status as EXPIRED (terminal status)."""
        ioc = cls.get_ioc(ioc_id)
        if not ioc:
            raise ValueError(f"IOC {ioc_id} not found")

        if ioc.status == IOCStatus.EXPIRED:
            return ioc

        ioc.status = IOCStatus.EXPIRED
        ioc.updated_at = datetime.now(timezone.utc)
        IOCHistoryService.record_event(
            ioc_id, "EXPIRED", "IOC marked as EXPIRED (terminal status)"
        )
        return ioc

    @classmethod
    def revoke_ioc(cls, ioc_id: uuid.UUID) -> IOCRecord:
        """Mark an IOC status as REVOKED (terminal status)."""
        ioc = cls.get_ioc(ioc_id)
        if not ioc:
            raise ValueError(f"IOC {ioc_id} not found")

        if ioc.status == IOCStatus.REVOKED:
            return ioc

        ioc.status = IOCStatus.REVOKED
        ioc.updated_at = datetime.now(timezone.utc)
        IOCHistoryService.record_event(
            ioc_id, "REVOKED", "IOC marked as REVOKED (terminal status)"
        )
        return ioc
