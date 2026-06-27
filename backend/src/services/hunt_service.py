import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.domain.entities.hunt import HuntResponse, HuntSeverity, HuntStatus, HuntType
from src.services.hunt_severity_registry import HuntSeverityRegistry
from src.services.hunt_type_registry import HuntTypeRegistry
from src.services.hunt_fingerprint_service import HuntFingerprintService
from src.services.hunt_history_service import HuntHistoryService


class HuntRecord:
    def __init__(
        self,
        hunt_id: uuid.UUID,
        hunt_fingerprint: str,
        title: str,
        description: str,
        hunt_type: HuntType,
        severity: HuntSeverity,
        status: HuntStatus,
        owner_id: Optional[uuid.UUID] = None,
        scope_id: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        related_entities: Optional[List[dict]] = None,
    ):
        self.hunt_id = hunt_id
        self.hunt_fingerprint = hunt_fingerprint
        self.title = title
        self.description = description
        self.hunt_type = hunt_type
        self.severity = severity
        self.status = status
        self.owner_id = owner_id
        self.scope_id = scope_id
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
        self.related_entities = related_entities or []


class HuntService:
    # in-memory store: hunt_id -> HuntRecord
    _hunts: Dict[uuid.UUID, HuntRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def clear_hunts(cls) -> None:
        """Clear all hunt records and references."""
        cls._hunts.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_hunts(cls) -> List[HuntRecord]:
        """Retrieve all hunt records."""
        return list(cls._hunts.values())

    @classmethod
    def get_hunt(cls, hunt_id: uuid.UUID) -> Optional[HuntRecord]:
        """Retrieve a hunt record by ID."""
        return cls._hunts.get(hunt_id)

    @classmethod
    def get_hunt_by_fingerprint(cls, fingerprint: str) -> Optional[HuntRecord]:
        """Retrieve a hunt record by fingerprint."""
        hunt_id = cls._fingerprint_lookup.get(fingerprint)
        if hunt_id:
            return cls.get_hunt(hunt_id)
        return None

    @classmethod
    def create_or_sync_hunt(
        cls,
        title: str,
        description: str,
        hunt_type: HuntType,
        severity: HuntSeverity,
        scope_id: Optional[uuid.UUID] = None,
        owner_id: Optional[uuid.UUID] = None,
        related_entities: Optional[List[dict]] = None,
    ) -> HuntRecord:
        """Create or synchronize a hunt record, enforcing identity and terminal states."""
        if not HuntTypeRegistry.is_valid_type(hunt_type):
            raise ValueError(f"Invalid hunt type: {hunt_type}")

        resolved_severity = HuntSeverityRegistry.resolve_severity(severity)
        entities = related_entities or []
        fingerprint = HuntFingerprintService.generate_fingerprint(hunt_type, title, entities)

        existing = cls.get_hunt_by_fingerprint(fingerprint)
        if existing:
            # Sync rules: preserve hunt_id, hypotheses, findings, history, timestamps, and status
            changed = False
            if existing.description != description:
                existing.description = description
                changed = True
            if existing.severity != resolved_severity:
                existing.severity = resolved_severity
                changed = True
            if owner_id and existing.owner_id != owner_id:
                existing.owner_id = owner_id
                changed = True
            if scope_id and existing.scope_id != scope_id:
                existing.scope_id = scope_id
                changed = True

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
                HuntHistoryService.record_event(
                    existing.hunt_id,
                    "UPDATED",
                    f"Hunt updated: severity={existing.severity.value}, status={existing.status.value}",
                )
            return existing

        # Create new hunt
        hunt_id = uuid.uuid4()
        record = HuntRecord(
            hunt_id=hunt_id,
            hunt_fingerprint=fingerprint,
            title=title,
            description=description,
            hunt_type=hunt_type,
            severity=resolved_severity,
            status=HuntStatus.OPEN,
            owner_id=owner_id,
            scope_id=scope_id,
            related_entities=entities,
        )
        cls._hunts[hunt_id] = record
        cls._fingerprint_lookup[fingerprint] = hunt_id

        HuntHistoryService.record_event(
            hunt_id,
            "CREATED",
            f"Created open threat hunt: '{title}' ({hunt_type.value})",
        )
        return record

    @classmethod
    def activate_hunt(cls, hunt_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> HuntRecord:
        """Transition hunt to ACTIVE status."""
        hunt = cls.get_hunt(hunt_id)
        if not hunt:
            raise ValueError(f"Hunt {hunt_id} not found")

        if hunt.status == HuntStatus.CLOSED:
            raise ValueError("CLOSED is a terminal state and cannot transition back to active")

        if hunt.status == HuntStatus.ACTIVE:
            return hunt

        hunt.status = HuntStatus.ACTIVE
        hunt.updated_at = datetime.now(timezone.utc)
        if user_id:
            hunt.owner_id = user_id

        HuntHistoryService.record_event(
            hunt_id, "ACTIVATED", f"Hunt activated. Owner assigned: {user_id}"
        )
        return hunt

    @classmethod
    def review_hunt(cls, hunt_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> HuntRecord:
        """Transition hunt to UNDER_REVIEW status."""
        hunt = cls.get_hunt(hunt_id)
        if not hunt:
            raise ValueError(f"Hunt {hunt_id} not found")

        if hunt.status == HuntStatus.CLOSED:
            raise ValueError("CLOSED is a terminal state and cannot transition back to active")

        if hunt.status == HuntStatus.UNDER_REVIEW:
            return hunt

        hunt.status = HuntStatus.UNDER_REVIEW
        hunt.updated_at = datetime.now(timezone.utc)
        HuntHistoryService.record_event(hunt_id, "UNDER_REVIEW", "Hunt transitioned to under review")
        return hunt

    @classmethod
    def complete_hunt(cls, hunt_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> HuntRecord:
        """Transition hunt to COMPLETED status."""
        hunt = cls.get_hunt(hunt_id)
        if not hunt:
            raise ValueError(f"Hunt {hunt_id} not found")

        if hunt.status == HuntStatus.CLOSED:
            raise ValueError("CLOSED is a terminal state and cannot transition back to active")

        if hunt.status == HuntStatus.COMPLETED:
            return hunt

        hunt.status = HuntStatus.COMPLETED
        hunt.updated_at = datetime.now(timezone.utc)
        HuntHistoryService.record_event(hunt_id, "COMPLETED", "Hunt successfully completed")
        return hunt

    @classmethod
    def close_hunt(cls, hunt_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> HuntRecord:
        """Transition hunt to CLOSED status (terminal state)."""
        hunt = cls.get_hunt(hunt_id)
        if not hunt:
            raise ValueError(f"Hunt {hunt_id} not found")

        if hunt.status == HuntStatus.CLOSED:
            return hunt

        hunt.status = HuntStatus.CLOSED
        hunt.updated_at = datetime.now(timezone.utc)
        HuntHistoryService.record_event(
            hunt_id, "CLOSED", "Hunt closed. This is a terminal state."
        )
        return hunt

    @classmethod
    def escalate_hunt(cls, hunt_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> HuntRecord:
        """Transition hunt to ESCALATED status."""
        hunt = cls.get_hunt(hunt_id)
        if not hunt:
            raise ValueError(f"Hunt {hunt_id} not found")

        if hunt.status == HuntStatus.CLOSED:
            raise ValueError("CLOSED is a terminal state and cannot transition back to active")

        if hunt.status == HuntStatus.ESCALATED:
            return hunt

        hunt.status = HuntStatus.ESCALATED
        hunt.updated_at = datetime.now(timezone.utc)
        HuntHistoryService.record_event(hunt_id, "ESCALATED", "Hunt escalated to higher priority")
        return hunt

    @classmethod
    def to_response(cls, record: HuntRecord) -> HuntResponse:
        """Convert a HuntRecord into a HuntResponse schema."""
        from src.services.hunt_finding_service import HuntFindingService
        from src.services.hunt_hypothesis_service import HuntHypothesisService

        hyps = HuntHypothesisService.get_hypotheses(record.hunt_id)
        finds = HuntFindingService.get_findings(record.hunt_id)

        return HuntResponse(
            hunt_id=record.hunt_id,
            hunt_fingerprint=record.hunt_fingerprint,
            title=record.title,
            description=record.description,
            hunt_type=record.hunt_type,
            severity=record.severity,
            status=record.status,
            owner_id=record.owner_id,
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            hypotheses=hyps,
            findings=finds,
            related_entities=record.related_entities,
        )
