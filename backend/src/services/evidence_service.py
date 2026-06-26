import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.case import ChainOfCustodyAction, EvidenceStatus
from src.services.workflow_event_service import WorkflowEventService


class EvidenceRecord:
    def __init__(
        self,
        evidence_id: uuid.UUID,
        case_id: uuid.UUID,
        source_entity: str,
        source_id: uuid.UUID,
        integrity_hash: str,
        status: EvidenceStatus,
        collected_by: uuid.UUID,
        collected_at: datetime,
        raw_data: str = "",
    ):
        self.evidence_id = evidence_id
        self.case_id = case_id
        self.source_entity = source_entity
        self.source_id = source_id
        self.integrity_hash = integrity_hash
        self.status = status
        self.collected_by = collected_by
        self.collected_at = collected_at
        self.raw_data = raw_data


class EvidenceService:
    # in-memory store: evidence_id -> EvidenceRecord
    _evidence: Dict[uuid.UUID, EvidenceRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def clear_evidence(cls) -> None:
        """Clear all in-memory evidence records."""
        cls._evidence.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_evidence(cls) -> List[EvidenceRecord]:
        """Retrieve all evidence records."""
        return list(cls._evidence.values())

    @classmethod
    def get_evidence_by_id(cls, evidence_id: uuid.UUID) -> Optional[EvidenceRecord]:
        """Retrieve evidence by ID."""
        return cls._evidence.get(evidence_id)

    @classmethod
    def generate_fingerprint(
        cls, source_entity: str, source_id: uuid.UUID, integrity_hash: str
    ) -> str:
        """Generate stable, deterministic fingerprint for evidence: SHA256(source_entity, source_id, integrity_hash)."""
        payload = f"{source_entity}:{source_id}:{integrity_hash}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def get_evidence_by_fingerprint(cls, fingerprint: str) -> Optional[EvidenceRecord]:
        """Retrieve evidence by fingerprint."""
        evidence_id = cls._fingerprint_lookup.get(fingerprint)
        if evidence_id:
            return cls.get_evidence_by_id(evidence_id)
        return None

    @classmethod
    def add_evidence(
        cls,
        case_id: uuid.UUID,
        source_entity: str,
        source_id: uuid.UUID,
        collected_by: uuid.UUID,
        raw_data: str,
        integrity_hash: Optional[str] = None,
    ) -> EvidenceRecord:
        """Add a new evidence record, enforcing stability and terminal state rules."""
        calculated_hash = integrity_hash or hashlib.sha256(raw_data.encode("utf-8")).hexdigest()
        fingerprint = cls.generate_fingerprint(source_entity, source_id, calculated_hash)

        existing = cls.get_evidence_by_fingerprint(fingerprint)
        if existing:
            # Enforce Archived Evidence Enforcement
            if existing.status == EvidenceStatus.ARCHIVED:
                raise ValueError("Evidence is ARCHIVED and cannot be modified or recollected.")

            # Evidence Identity Preservation Rule: Only update mutable metadata (like case_id)
            existing.case_id = case_id
            return existing

        evidence_id = uuid.uuid4()
        record = EvidenceRecord(
            evidence_id=evidence_id,
            case_id=case_id,
            source_entity=source_entity,
            source_id=source_id,
            integrity_hash=calculated_hash,
            status=EvidenceStatus.COLLECTED,
            collected_by=collected_by,
            collected_at=datetime.now(timezone.utc),
            raw_data=raw_data,
        )
        cls._evidence[evidence_id] = record
        cls._fingerprint_lookup[fingerprint] = evidence_id

        # Record initial custody entry
        from src.services.custody_service import CustodyService
        CustodyService.record_custody_event(
            evidence_id=evidence_id,
            action=ChainOfCustodyAction.COLLECTED,
            actor=collected_by,
            notes="Evidence collected.",
            integrity_verified=True,
        )

        return record

    @classmethod
    def verify_integrity_check(cls, evidence: EvidenceRecord) -> bool:
        """Check if raw data hashes to integrity_hash."""
        calculated_hash = hashlib.sha256(evidence.raw_data.encode("utf-8")).hexdigest()
        return calculated_hash == evidence.integrity_hash

    @classmethod
    async def verify_evidence_integrity(
        cls,
        db: AsyncSession,
        evidence_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> bool:
        """Verify the forensic integrity of evidence and log verified action to custody chain."""
        evidence = cls.get_evidence_by_id(evidence_id)
        if not evidence:
            raise ValueError("Evidence not found.")

        is_valid = cls.verify_integrity_check(evidence)

        # Record custody verified event
        from src.services.custody_service import CustodyService
        CustodyService.record_custody_event(
            evidence_id=evidence_id,
            action=ChainOfCustodyAction.VERIFIED,
            actor=actor_id,
            notes=f"Integrity verification: {'PASSED' if is_valid else 'FAILED'}",
            integrity_verified=is_valid,
        )

        if not is_valid:
            # Emit workflow event for integrity failure
            await WorkflowEventService.emit_event(
                db=db,
                event_type="evidence.integrity_failed",
                payload={
                    "evidence_id": str(evidence_id),
                    "case_id": str(evidence.case_id),
                    "source_entity": evidence.source_entity,
                    "source_id": str(evidence.source_id),
                },
            )
        else:
            if evidence.status != EvidenceStatus.ARCHIVED:
                evidence.status = EvidenceStatus.VERIFIED

        return is_valid

    @classmethod
    def transfer_evidence(
        cls,
        evidence_id: uuid.UUID,
        new_case_id: uuid.UUID,
        actor_id: uuid.UUID,
        notes: str = "",
    ) -> EvidenceRecord:
        """Transfer evidence to another case and log transfer event in chain of custody."""
        evidence = cls.get_evidence_by_id(evidence_id)
        if not evidence:
            raise ValueError("Evidence not found.")

        if evidence.status == EvidenceStatus.ARCHIVED:
            raise ValueError("Evidence is ARCHIVED and cannot be transferred.")

        evidence.case_id = new_case_id
        evidence.status = EvidenceStatus.TRANSFERRED

        from src.services.custody_service import CustodyService
        CustodyService.record_custody_event(
            evidence_id=evidence_id,
            action=ChainOfCustodyAction.TRANSFERRED,
            actor=actor_id,
            notes=notes or f"Transferred to case {new_case_id}",
            integrity_verified=cls.verify_integrity_check(evidence),
        )

        return evidence

    @classmethod
    def archive_evidence(
        cls,
        evidence_id: uuid.UUID,
        actor_id: uuid.UUID,
        notes: str = "",
    ) -> EvidenceRecord:
        """Archive evidence record (terminal status change)."""
        evidence = cls.get_evidence_by_id(evidence_id)
        if not evidence:
            raise ValueError("Evidence not found.")

        if evidence.status == EvidenceStatus.ARCHIVED:
            return evidence

        evidence.status = EvidenceStatus.ARCHIVED

        from src.services.custody_service import CustodyService
        CustodyService.record_custody_event(
            evidence_id=evidence_id,
            action=ChainOfCustodyAction.ARCHIVED,
            actor=actor_id,
            notes=notes or "Evidence archived.",
            integrity_verified=cls.verify_integrity_check(evidence),
        )

        return evidence
