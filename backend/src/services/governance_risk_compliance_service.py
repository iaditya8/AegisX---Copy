import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.governance_risk_compliance import (
    ComplianceStatus,
    FrameworkType,
    ComplianceAssessmentResponse,
    ComplianceEvidenceResponse,
)
from src.services.compliance_fingerprint_service import ComplianceFingerprintService
from src.services.compliance_history_service import ComplianceHistoryService
from src.services.control_mapping_registry import ControlMappingRegistry
from src.services.compliance_scoring_service import ComplianceScoringService
from src.services.audit_readiness_service import AuditReadinessService


class GRCRecord:
    def __init__(
        self,
        assessment_id: uuid.UUID,
        assessment_fingerprint: str,
        framework_type: FrameworkType,
        name: str,
        description: str,
        compliance_score: float,
        framework_coverage: float,
        control_coverage: float,
        evidence_completeness: float,
        audit_readiness: float,
        status: ComplianceStatus,
        scope_id: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.assessment_id = assessment_id
        self.assessment_fingerprint = assessment_fingerprint
        self.framework_type = framework_type
        self.name = name
        self.description = description
        self.compliance_score = compliance_score
        self.framework_coverage = framework_coverage
        self.control_coverage = control_coverage
        self.evidence_completeness = evidence_completeness
        self.audit_readiness = audit_readiness
        self.status = status
        self.scope_id = scope_id
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
        self.evidence_list: List[ComplianceEvidenceResponse] = []


from src.infrastructure.cache.cache_dict import CacheDict


class GovernanceRiskComplianceService:
    # in-memory store: assessment_id -> GRCRecord
    _assessments = CacheDict("grc_compliance")
    _fingerprint_lookup = CacheDict("grc_compliance_fingerprints")

    ALLOWED_TRANSITIONS = {
        ComplianceStatus.ACTIVE: {
            ComplianceStatus.IN_REVIEW,
            ComplianceStatus.COMPLIANT,
            ComplianceStatus.NON_COMPLIANT,
            ComplianceStatus.CLOSED,
        },
        ComplianceStatus.IN_REVIEW: {
            ComplianceStatus.COMPLIANT,
            ComplianceStatus.NON_COMPLIANT,
            ComplianceStatus.CLOSED,
        },
        ComplianceStatus.COMPLIANT: {ComplianceStatus.CLOSED},
        ComplianceStatus.NON_COMPLIANT: {ComplianceStatus.CLOSED},
        ComplianceStatus.CLOSED: set(),  # Terminal
    }

    @classmethod
    def clear_assessments(cls) -> None:
        """Clear all GRC records and lookup cache."""
        cls._assessments.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_assessments(cls) -> List[GRCRecord]:
        """Retrieve all GRC records."""
        return list(cls._assessments.values())

    @classmethod
    def get_assessment(cls, assessment_id: uuid.UUID) -> Optional[GRCRecord]:
        """Retrieve a GRC record by ID."""
        return cls._assessments.get(assessment_id)

    @classmethod
    def get_assessment_by_fingerprint(cls, fingerprint: str) -> Optional[GRCRecord]:
        """Retrieve a GRC record by fingerprint."""
        assessment_id = cls._fingerprint_lookup.get(fingerprint)
        if assessment_id:
            return cls.get_assessment(assessment_id)
        return None

    @classmethod
    async def create_or_sync_assessment(
        cls,
        name: str,
        description: str,
        framework_type: FrameworkType,
        scope_id: Optional[uuid.UUID] = None,
    ) -> GRCRecord:
        """Create or synchronize GRC assessment record enforcing identity rules."""
        fingerprint = ComplianceFingerprintService.generate_fingerprint(
            framework_type.value, name, scope_id
        )
        existing = cls.get_assessment_by_fingerprint(fingerprint)

        # Retrieve standard mapped controls
        controls = ControlMappingRegistry.get_controls(framework_type)
        control_count = len(controls)
        evidence_count = len(existing.evidence_list) if existing else 0

        scores = ComplianceScoringService.calculate_scores(control_count, evidence_count)
        readiness = AuditReadinessService.calculate_readiness(
            scores["compliance_score"], scores["evidence_completeness"]
        )

        if existing:
            if existing.status == ComplianceStatus.CLOSED:
                # Terminal State Rule
                return existing

            changed = False
            if existing.framework_coverage != scores["framework_coverage"]:
                existing.framework_coverage = scores["framework_coverage"]
                changed = True
            if existing.compliance_score != scores["compliance_score"]:
                existing.compliance_score = scores["compliance_score"]
                changed = True
                ComplianceHistoryService.record_event(
                    existing.assessment_id, "SCORE_CHANGED", f"Compliance score updated to {scores['compliance_score']}"
                )
            if existing.audit_readiness != readiness:
                existing.audit_readiness = readiness
                changed = True

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
            return existing

        # Create new record
        assessment_id = uuid.uuid4()

        record = GRCRecord(
            assessment_id=assessment_id,
            assessment_fingerprint=fingerprint,
            framework_type=framework_type,
            name=name,
            description=description,
            compliance_score=scores["compliance_score"],
            framework_coverage=scores["framework_coverage"],
            control_coverage=scores["control_coverage"],
            evidence_completeness=scores["evidence_completeness"],
            audit_readiness=readiness,
            status=ComplianceStatus.ACTIVE,
            scope_id=scope_id,
        )

        cls._assessments[assessment_id] = record
        cls._fingerprint_lookup[fingerprint] = assessment_id

        ComplianceHistoryService.record_event(
            assessment_id, "CREATED", f"Compliance assessment created: '{name}'"
        )
        return record

    @classmethod
    async def add_evidence(
        cls,
        assessment_id: uuid.UUID,
        file_name: str,
        file_hash: str,
    ) -> ComplianceEvidenceResponse:
        """Add audit evidence hash to compliance record, re-evaluating compliance score."""
        record = cls.get_assessment(assessment_id)
        if not record:
            raise ValueError(f"Assessment {assessment_id} not found")

        if record.status == ComplianceStatus.CLOSED:
            raise ValueError("Cannot add evidence to a closed assessment")

        evidence = ComplianceEvidenceResponse(
            evidence_id=uuid.uuid4(),
            assessment_id=assessment_id,
            file_name=file_name,
            file_hash=file_hash,
            uploaded_at=datetime.now(timezone.utc),
        )
        record.evidence_list.append(evidence)

        # Recalculate GRC metrics
        controls = ControlMappingRegistry.get_controls(record.framework_type)
        control_count = len(controls)
        evidence_count = len(record.evidence_list)

        scores = ComplianceScoringService.calculate_scores(control_count, evidence_count)
        readiness = AuditReadinessService.calculate_readiness(
            scores["compliance_score"], scores["evidence_completeness"]
        )

        record.compliance_score = scores["compliance_score"]
        record.framework_coverage = scores["framework_coverage"]
        record.evidence_completeness = scores["evidence_completeness"]
        record.audit_readiness = readiness
        record.updated_at = datetime.now(timezone.utc)

        ComplianceHistoryService.record_event(
            assessment_id, "EVIDENCE_ADDED", f"Evidence uploaded: '{file_name}' (Hash: {file_hash})"
        )
        return evidence

    @classmethod
    async def sync_assessments(cls, db: AsyncSession) -> List[GRCRecord]:
        """Continuous sync loop discovering current governance compliance posture."""
        synced = []

        # 1. ISO27001 Security Assessment
        rec1 = await cls.create_or_sync_assessment(
            name="ISO27001 Security Assessment",
            description="Standard ISO compliance checklist.",
            framework_type=FrameworkType.ISO27001,
        )
        synced.append(rec1)

        # 2. SOC2 Trust Services Criteria
        rec2 = await cls.create_or_sync_assessment(
            name="SOC2 Trust Services Criteria",
            description="TSC security criteria verification.",
            framework_type=FrameworkType.SOC2,
        )
        synced.append(rec2)

        return synced

    @classmethod
    def transition_status(
        cls, assessment_id: uuid.UUID, new_status: ComplianceStatus
    ) -> GRCRecord:
        """Safely transition GRC status enforcing forward-only rules and terminal states."""
        record = cls.get_assessment(assessment_id)
        if not record:
            raise ValueError(f"Assessment {assessment_id} not found")

        if record.status == ComplianceStatus.CLOSED:
            # Terminal State Rule
            return record

        allowed = cls.ALLOWED_TRANSITIONS.get(record.status, set())
        if new_status not in allowed:
            raise ValueError(f"Invalid transition from {record.status.value} to {new_status.value}")

        old_status = record.status
        record.status = new_status
        record.updated_at = datetime.now(timezone.utc)

        event_map = {
            ComplianceStatus.IN_REVIEW: "IN_REVIEW",
            ComplianceStatus.COMPLIANT: "COMPLIANT",
            ComplianceStatus.NON_COMPLIANT: "NON_COMPLIANT",
            ComplianceStatus.CLOSED: "CLOSED",
        }
        event_type = event_map.get(new_status, "STATUS_CHANGED")

        ComplianceHistoryService.record_event(
            assessment_id,
            event_type,
            f"Status transitioned from {old_status.value} to {new_status.value}",
        )
        return record

    @classmethod
    def recalculate_assessments(cls) -> None:
        """Recalculate GRC assessment scores and statuses deterministically (derived intelligence)."""
        for record in cls.get_all_assessments():
            if record.status == ComplianceStatus.CLOSED:
                continue

            controls = ControlMappingRegistry.get_controls(record.framework_type)
            control_count = len(controls)
            evidence_count = len(record.evidence_list)

            scores = ComplianceScoringService.calculate_scores(control_count, evidence_count)
            readiness = AuditReadinessService.calculate_readiness(
                scores["compliance_score"], scores["evidence_completeness"]
            )

            changed = False
            if record.framework_coverage != scores["framework_coverage"]:
                record.framework_coverage = scores["framework_coverage"]
                changed = True
            if record.compliance_score != scores["compliance_score"]:
                old_score = record.compliance_score
                record.compliance_score = scores["compliance_score"]
                changed = True
                ComplianceHistoryService.record_event(
                    record.assessment_id, "RECALCULATED", f"Recalculated compliance score changed from {old_score} to {scores['compliance_score']}"
                )
            if record.control_coverage != scores["control_coverage"]:
                record.control_coverage = scores["control_coverage"]
                changed = True
            if record.evidence_completeness != scores["evidence_completeness"]:
                record.evidence_completeness = scores["evidence_completeness"]
                changed = True
            if record.audit_readiness != readiness:
                record.audit_readiness = readiness
                changed = True

            if changed:
                record.updated_at = datetime.now(timezone.utc)

    @classmethod
    def to_response(cls, record: GRCRecord) -> ComplianceAssessmentResponse:
        return ComplianceAssessmentResponse(
            assessment_id=record.assessment_id,
            assessment_fingerprint=record.assessment_fingerprint,
            framework_type=record.framework_type,
            name=record.name,
            description=record.description,
            compliance_score=record.compliance_score,
            framework_coverage=record.framework_coverage,
            control_coverage=record.control_coverage,
            evidence_completeness=record.evidence_completeness,
            audit_readiness=record.audit_readiness,
            status=record.status,
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
