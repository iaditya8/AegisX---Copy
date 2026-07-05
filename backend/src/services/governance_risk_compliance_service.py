import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.tenant import get_current_tenant_id
from src.domain.entities.governance_risk_compliance import (
    ComplianceStatus,
    FrameworkType,
    ComplianceAssessmentResponse,
    ComplianceEvidenceResponse,
)
from src.infrastructure.database.models import GRCAssessment, GRCFrameworkControl, GRCEvidence, GRCGap, GRCHistory, IntelligenceEvent, AuditLog
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.services.compliance_fingerprint_service import ComplianceFingerprintService
from src.services.compliance_history_service import ComplianceHistoryService
from src.services.control_mapping_registry import ControlMappingRegistry
from src.services.compliance_scoring_service import ComplianceScoringService
from src.services.audit_readiness_service import AuditReadinessService
from src.infrastructure.cache.cache_dict import CacheDict


class GovernanceRiskComplianceService:
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
    async def get_all_assessments(cls) -> List[GRCAssessment]:
        """Retrieve all GRC records."""
        async with UnitOfWork() as uow:
            tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
            records = await uow.grc_repo.get_active_assessments(tenant_id)
            for r in records:
                # dynamically attach evidence list
                r.evidence_list = await uow.grc_repo.get_evidence(r.id)
                cls._assessments[r.id] = r
                cls._fingerprint_lookup[r.assessment_fingerprint] = r.id
            return records

    @classmethod
    async def get_assessment(cls, assessment_id: uuid.UUID) -> Optional[GRCAssessment]:
        """Retrieve a GRC record by ID."""
        cached = cls._assessments.get(assessment_id)
        if cached:
            # ensure evidence list is attached
            if not hasattr(cached, "evidence_list"):
                async with UnitOfWork() as uow:
                    cached.evidence_list = await uow.grc_repo.get_evidence(cached.id)
            return cached

        async with UnitOfWork() as uow:
            record = await uow.grc_repo.get_by_id(assessment_id)
            if record:
                record.evidence_list = await uow.grc_repo.get_evidence(record.id)
                cls._assessments[record.id] = record
                cls._fingerprint_lookup[record.assessment_fingerprint] = record.id
                return record
        return None

    @classmethod
    async def get_assessment_by_fingerprint(cls, fingerprint: str) -> Optional[GRCAssessment]:
        """Retrieve a GRC record by fingerprint."""
        assessment_id = cls._fingerprint_lookup.get(fingerprint)
        if assessment_id:
            cached = await cls.get_assessment(assessment_id)
            if cached:
                return cached
        async with UnitOfWork() as uow:
            tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
            record = await uow.grc_repo.get_by_fingerprint(tenant_id, fingerprint)
            if record:
                record.evidence_list = await uow.grc_repo.get_evidence(record.id)
                cls._assessments[record.id] = record
                cls._fingerprint_lookup[record.assessment_fingerprint] = record.id
                return record
        return None

    @classmethod
    async def create_or_sync_assessment(
        cls,
        name: str,
        description: str,
        framework_type: FrameworkType,
        scope_id: Optional[uuid.UUID] = None,
        uow: Optional[UnitOfWork] = None,
    ) -> GRCAssessment:
        """Create or synchronize GRC assessment record enforcing identity rules."""
        fingerprint = ComplianceFingerprintService.generate_fingerprint(
            framework_type.value, name, scope_id
        )
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        async def _sync(uow_inst: UnitOfWork) -> GRCAssessment:
            existing = await uow_inst.grc_repo.get_by_fingerprint(tenant_id, fingerprint)
            if existing:
                existing.evidence_list = await uow_inst.grc_repo.get_evidence(existing.id)
            
            # Retrieve standard mapped controls
            controls = ControlMappingRegistry.get_controls(framework_type)
            control_count = len(controls)
            evidence_count = len(existing.evidence_list) if existing else 0

            scores = ComplianceScoringService.calculate_scores(control_count, evidence_count)
            readiness = AuditReadinessService.calculate_readiness(
                scores["compliance_score"], scores["evidence_completeness"]
            )

            if existing:
                if existing.status == ComplianceStatus.CLOSED.value:
                    return existing

                changed = False
                if float(existing.framework_coverage) != scores["framework_coverage"]:
                    existing.framework_coverage = scores["framework_coverage"]
                    changed = True
                if float(existing.compliance_score) != scores["compliance_score"]:
                    existing.compliance_score = scores["compliance_score"]
                    changed = True
                    # Record history
                    hist = GRCHistory(
                        assessment_id=existing.id,
                        event_type="SCORE_CHANGED",
                        details=f"Compliance score updated to {scores['compliance_score']}",
                        tenant_id=tenant_id
                    )
                    uow_inst.session.add(hist)
                if float(existing.audit_readiness) != readiness:
                    existing.audit_readiness = readiness
                    changed = True

                if changed:
                    existing.updated_at = datetime.now(timezone.utc)
                    existing.version += 1
                    
                    event = IntelligenceEvent(
                        tenant_id=tenant_id,
                        domain="grc",
                        entity_id=existing.id,
                        event_type="grc.assessment.updated",
                        payload={"id": str(existing.id), "name": existing.name, "compliance_score": float(existing.compliance_score)},
                        status="pending"
                    )
                    uow_inst.session.add(event)
                    
                    audit = AuditLog(
                        tenant_id=tenant_id,
                        actor_id=existing.created_by,
                        action="update_assessment",
                        target_type="assessment",
                        target_id=existing.id,
                        metadata_json={"name": existing.name},
                        timestamp=datetime.now(timezone.utc)
                    )
                    uow_inst.session.add(audit)

                return existing

            # Create new record
            record = GRCAssessment(
                assessment_fingerprint=fingerprint,
                framework_type=framework_type.value,
                name=name,
                description=description,
                compliance_score=scores["compliance_score"],
                framework_coverage=scores["framework_coverage"],
                control_coverage=scores["control_coverage"],
                evidence_completeness=scores["evidence_completeness"],
                audit_readiness=readiness,
                status=ComplianceStatus.ACTIVE.value,
                scope_id=scope_id,
                tenant_id=tenant_id,
                version=1
            )
            await uow_inst.grc_repo.save(record)
            await uow_inst.session.flush()

            # Seeding mapped GRC framework controls to DB
            for ctrl in controls:
                db_ctrl = GRCFrameworkControl(
                    control_name=ctrl.control_name,
                    framework_type=framework_type.value,
                    requirement_id=ctrl.requirement_id,
                    status="PENDING",
                    tenant_id=tenant_id,
                    version=1
                )
                await uow_inst.grc_repo.save_control(db_ctrl)

            # Record history
            hist = GRCHistory(
                assessment_id=record.id,
                event_type="CREATED",
                details=f"Compliance assessment created: '{name}'",
                tenant_id=tenant_id
            )
            uow_inst.session.add(hist)

            # Outbox Event
            event = IntelligenceEvent(
                tenant_id=tenant_id,
                domain="grc",
                entity_id=record.id,
                event_type="grc.assessment.created",
                payload={"id": str(record.id), "name": record.name, "compliance_score": float(record.compliance_score)},
                status="pending"
            )
            uow_inst.session.add(event)

            # Audit Log
            audit = AuditLog(
                tenant_id=tenant_id,
                actor_id=None,
                action="create_assessment",
                target_type="assessment",
                target_id=record.id,
                metadata_json={"name": record.name},
                timestamp=datetime.now(timezone.utc)
            )
            uow_inst.session.add(audit)

            record.evidence_list = []
            return record

        if uow:
            rec = await _sync(uow)
            cls._assessments[rec.id] = rec
            cls._fingerprint_lookup[rec.assessment_fingerprint] = rec.id
            return rec
        else:
            async with UnitOfWork() as new_uow:
                rec = await _sync(new_uow)
                await new_uow.commit()
                cls._assessments[rec.id] = rec
                cls._fingerprint_lookup[rec.assessment_fingerprint] = rec.id
                return rec

    @classmethod
    async def add_evidence(
        cls,
        assessment_id: uuid.UUID,
        file_name: str,
        file_hash: str,
    ) -> ComplianceEvidenceResponse:
        """Add audit evidence hash to compliance record, re-evaluating compliance score."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            record = await uow.grc_repo.get_by_id(assessment_id)
            if not record or record.is_deleted:
                raise ValueError(f"Assessment {assessment_id} not found")

            if record.status == ComplianceStatus.CLOSED.value:
                raise ValueError("Cannot add evidence to a closed assessment")

            evidence = GRCEvidence(
                assessment_id=assessment_id,
                file_name=file_name,
                evidence_uri=f"s3://aegisx-compliance-evidence/{tenant_id}/{assessment_id}/{file_name}",
                evidence_hash=file_hash,
                content_type="application/octet-stream",
                size_bytes=1024, # mock size
                tenant_id=tenant_id,
                version=1
            )
            await uow.grc_repo.save_evidence(evidence)
            await uow.session.flush()

            # Fetch updated evidence list
            record.evidence_list = await uow.grc_repo.get_evidence(record.id)

            # Recalculate GRC metrics
            controls = ControlMappingRegistry.get_controls(FrameworkType(record.framework_type))
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
            record.version += 1

            # Gaps / Compliance Gap creation if needed
            # For demonstration, standard evidence might trigger gap check
            if scores["compliance_score"] < 100.0 and evidence_count == 1:
                # Auto-generate a compliance gap for first missing control
                gap = GRCGap(
                    assessment_id=assessment_id,
                    gap_type="MISSING_EVIDENCE",
                    description="Compliance gap identified: control framework contains unmapped requirements.",
                    remediation_plan="Upload verifying documents for remaining controls.",
                    tenant_id=tenant_id,
                    version=1
                )
                await uow.grc_repo.save_gap(gap)
                await uow.session.flush()

                # Emit Outbox Event for gap
                gap_event = IntelligenceEvent(
                    tenant_id=tenant_id,
                    domain="grc",
                    entity_id=gap.id,
                    event_type="grc.gap.created",
                    payload={"id": str(gap.id), "assessment_id": str(assessment_id)},
                    status="pending"
                )
                uow.session.add(gap_event)

            # Record history
            hist = GRCHistory(
                assessment_id=assessment_id,
                event_type="EVIDENCE_ADDED",
                details=f"Evidence uploaded: '{file_name}' (Hash: {file_hash})",
                tenant_id=tenant_id
            )
            uow.session.add(hist)

            # Outbox Event
            event = IntelligenceEvent(
                tenant_id=tenant_id,
                domain="grc",
                entity_id=evidence.id,
                event_type="grc.evidence.added",
                payload={"id": str(evidence.id), "file_name": file_name, "file_hash": file_hash},
                status="pending"
            )
            uow.session.add(event)

            # Audit Log
            audit = AuditLog(
                tenant_id=tenant_id,
                actor_id=record.created_by,
                action="upload_evidence",
                target_type="evidence",
                target_id=evidence.id,
                metadata_json={"file_name": file_name},
                timestamp=datetime.now(timezone.utc)
            )
            uow.session.add(audit)

            await uow.commit()

            # Refresh cache
            cls._assessments[record.id] = record
            cls._fingerprint_lookup[record.assessment_fingerprint] = record.id

            return ComplianceEvidenceResponse(
                evidence_id=evidence.id,
                assessment_id=evidence.assessment_id,
                file_name=evidence.file_name,
                file_hash=evidence.evidence_hash,
                uploaded_at=evidence.created_at
            )

    @classmethod
    async def sync_assessments(cls, db: AsyncSession) -> List[GRCAssessment]:
        """Continuous sync loop GRC compliance bases."""
        synced = []
        async with UnitOfWork() as uow:
            rec1 = await cls.create_or_sync_assessment(
                name="ISO27001 Security Assessment",
                description="Standard ISO compliance checklist.",
                framework_type=FrameworkType.ISO27001,
                uow=uow
            )
            synced.append(rec1)

            rec2 = await cls.create_or_sync_assessment(
                name="SOC2 Trust Services Criteria",
                description="TSC security criteria verification.",
                framework_type=FrameworkType.SOC2,
                uow=uow
            )
            synced.append(rec2)
            await uow.commit()

        for r in synced:
            cls._assessments[r.id] = r
            cls._fingerprint_lookup[r.assessment_fingerprint] = r.id

        return synced

    @classmethod
    async def transition_status(
        cls, assessment_id: uuid.UUID, new_status: ComplianceStatus
    ) -> GRCAssessment:
        """Safely transition GRC status enforcing forward-only rules and terminal states."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            record = await uow.grc_repo.get_by_id(assessment_id)
            if not record:
                raise ValueError(f"Assessment {assessment_id} not found")

            current_status_enum = ComplianceStatus(record.status)
            if current_status_enum == ComplianceStatus.CLOSED:
                return record

            allowed = cls.ALLOWED_TRANSITIONS.get(current_status_enum, set())
            if new_status not in allowed:
                raise ValueError(f"Invalid transition from {record.status} to {new_status.value}")

            old_status = record.status
            record.status = new_status.value
            record.updated_at = datetime.now(timezone.utc)
            record.version += 1

            event_map = {
                ComplianceStatus.IN_REVIEW: "IN_REVIEW",
                ComplianceStatus.COMPLIANT: "COMPLIANT",
                ComplianceStatus.NON_COMPLIANT: "NON_COMPLIANT",
                ComplianceStatus.CLOSED: "CLOSED",
            }
            event_type = event_map.get(new_status, "STATUS_CHANGED")

            hist = GRCHistory(
                assessment_id=record.id,
                event_type=event_type,
                details=f"Status transitioned from {old_status} to {new_status.value}",
                tenant_id=tenant_id
            )
            uow.session.add(hist)

            event = IntelligenceEvent(
                tenant_id=tenant_id,
                domain="grc",
                entity_id=record.id,
                event_type="grc.assessment.updated" if new_status != ComplianceStatus.CLOSED else "grc.assessment.archived",
                payload={"id": str(record.id), "status": record.status},
                status="pending"
            )
            uow.session.add(event)

            audit = AuditLog(
                tenant_id=tenant_id,
                actor_id=record.created_by,
                action="transition_assessment",
                target_type="assessment",
                target_id=record.id,
                metadata_json={"old_status": old_status, "new_status": record.status},
                timestamp=datetime.now(timezone.utc)
            )
            uow.session.add(audit)

            await uow.commit()

            # reload fresh evidence
            record.evidence_list = await uow.grc_repo.get_evidence(record.id)
            cls._assessments[record.id] = record
            cls._fingerprint_lookup[record.assessment_fingerprint] = record.id
            return record

    @classmethod
    async def recalculate_assessments(cls) -> None:
        """Recalculate GRC assessment scores and statuses deterministically (derived intelligence)."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            records = await uow.grc_repo.get_active_assessments(tenant_id)
            for record in records:
                if record.status == ComplianceStatus.CLOSED.value:
                    continue

                record.evidence_list = await uow.grc_repo.get_evidence(record.id)

                controls = ControlMappingRegistry.get_controls(FrameworkType(record.framework_type))
                control_count = len(controls)
                evidence_count = len(record.evidence_list)

                scores = ComplianceScoringService.calculate_scores(control_count, evidence_count)
                readiness = AuditReadinessService.calculate_readiness(
                    scores["compliance_score"], scores["evidence_completeness"]
                )

                changed = False
                if float(record.framework_coverage) != scores["framework_coverage"]:
                    record.framework_coverage = scores["framework_coverage"]
                    changed = True
                if float(record.compliance_score) != scores["compliance_score"]:
                    old_score = record.compliance_score
                    record.compliance_score = scores["compliance_score"]
                    changed = True
                    hist = GRCHistory(
                        assessment_id=record.id,
                        event_type="RECALCULATED",
                        details=f"Recalculated compliance score changed from {old_score} to {scores['compliance_score']}",
                        tenant_id=tenant_id
                    )
                    uow.session.add(hist)
                if float(record.control_coverage) != scores["control_coverage"]:
                    record.control_coverage = scores["control_coverage"]
                    changed = True
                if float(record.evidence_completeness) != scores["evidence_completeness"]:
                    record.evidence_completeness = scores["evidence_completeness"]
                    changed = True
                if float(record.audit_readiness) != readiness:
                    record.audit_readiness = readiness
                    changed = True

                if changed:
                    record.updated_at = datetime.now(timezone.utc)
                    record.version += 1
                    
                    event = IntelligenceEvent(
                        tenant_id=tenant_id,
                        domain="grc",
                        entity_id=record.id,
                        event_type="grc.assessment.updated",
                        payload={"id": str(record.id), "compliance_score": float(record.compliance_score)},
                        status="pending"
                    )
                    uow.session.add(event)

            await uow.commit()

            # Refresh cache
            for r in records:
                cls._assessments[r.id] = r
                cls._fingerprint_lookup[r.assessment_fingerprint] = r.id

    @classmethod
    def to_response(cls, record: GRCAssessment) -> ComplianceAssessmentResponse:
        return ComplianceAssessmentResponse(
            assessment_id=record.id,
            assessment_fingerprint=record.assessment_fingerprint,
            framework_type=FrameworkType(record.framework_type),
            name=record.name,
            description=record.description,
            compliance_score=float(record.compliance_score),
            framework_coverage=float(record.framework_coverage),
            control_coverage=float(record.control_coverage),
            evidence_completeness=float(record.evidence_completeness),
            audit_readiness=float(record.audit_readiness),
            status=ComplianceStatus(record.status),
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
