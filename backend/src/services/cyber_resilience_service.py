from typing import List, Optional
import uuid
from datetime import datetime, timezone
from sqlalchemy.future import select
from src.core.tenant import get_current_tenant_id
from src.domain.entities.cyber_resilience import (
    ResilienceStatus,
    ServiceCriticality,
    CyberResilienceResponse,
    RecoveryObjectiveType,
)
from src.infrastructure.database.models import CyberResilienceRecord
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.services.resilience_fingerprint_service import ResilienceFingerprintService
from src.services.resilience_history_service import ResilienceHistoryService
from src.services.recovery_objective_service import RecoveryObjectiveService
from src.services.resilience_scoring_service import ResilienceScoringService


class CyberResilienceService:
    ALLOWED_TRANSITIONS = {
        ResilienceStatus.PLANNED: {ResilienceStatus.ACTIVE},
        ResilienceStatus.ACTIVE: {
            ResilienceStatus.UNDER_REVIEW,
            ResilienceStatus.VALIDATED,
            ResilienceStatus.COMPLETED,
            ResilienceStatus.CLOSED,
        },
        ResilienceStatus.UNDER_REVIEW: {
            ResilienceStatus.VALIDATED,
            ResilienceStatus.COMPLETED,
            ResilienceStatus.CLOSED,
        },
        ResilienceStatus.VALIDATED: {ResilienceStatus.COMPLETED, ResilienceStatus.CLOSED},
        ResilienceStatus.COMPLETED: set(),  # Terminal
        ResilienceStatus.CLOSED: set(),     # Terminal
    }

    @classmethod
    async def clear_resilience(cls) -> None:
        """Clear all resilience records."""
        pass

    @classmethod
    async def get_all_resilience(cls) -> List[CyberResilienceRecord]:
        """Retrieve all resilience records."""
        async with UnitOfWork() as uow:
            return await uow.resilience_repo.list()

    @classmethod
    async def get_resilience(cls, resilience_id: uuid.UUID) -> Optional[CyberResilienceRecord]:
        """Retrieve a resilience record by ID."""
        async with UnitOfWork() as uow:
            return await uow.resilience_repo.get(resilience_id)

    @classmethod
    async def get_resilience_by_fingerprint(cls, fingerprint: str, uow: Optional[UnitOfWork] = None) -> Optional[CyberResilienceRecord]:
        """Retrieve a resilience record by fingerprint."""
        async def _get(uow_inst: UnitOfWork) -> Optional[CyberResilienceRecord]:
            stmt = select(CyberResilienceRecord).filter_by(resilience_fingerprint=fingerprint)
            res = await uow_inst.session.execute(stmt)
            return res.scalar_one_or_none()

        if uow:
            return await _get(uow)
        else:
            async with UnitOfWork() as uow_new:
                return await _get(uow_new)

    @classmethod
    async def create_or_sync_resilience(
        cls,
        title: str,
        description: str,
        service_name: str,
        service_criticality: ServiceCriticality,
        scope_id: Optional[uuid.UUID] = None,
        uow: Optional[UnitOfWork] = None,
    ) -> CyberResilienceRecord:
        """Create or synchronize a cyber resilience record based on identity rules."""
        fingerprint = ResilienceFingerprintService.generate_fingerprint(
            title, service_name, service_criticality.value
        )
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        async def _sync(uow_inst: UnitOfWork) -> CyberResilienceRecord:
            existing = await cls.get_resilience_by_fingerprint(fingerprint, uow=uow_inst)
            if existing:
                if existing.status in (ResilienceStatus.COMPLETED.value, ResilienceStatus.CLOSED.value):
                    # Terminal State Rule
                    return existing

                # Calculate scores
                obj_comp = await RecoveryObjectiveService.get_resilience_objective_compliance(existing.resilience_id, uow=uow_inst)
                readiness = ResilienceScoringService.calculate_readiness_score(existing.resilience_id, ResilienceStatus(existing.status))
                confidence = ResilienceScoringService.calculate_recovery_confidence_score(
                    existing.resilience_id, ResilienceStatus(existing.status), obj_comp, readiness
                )
                resilience_score = ResilienceScoringService.calculate_resilience_score(
                    existing.resilience_id, ResilienceStatus(existing.status), ServiceCriticality(existing.service_criticality), readiness, obj_comp
                )

                changed = False
                if float(existing.resilience_score) != resilience_score:
                    existing.resilience_score = resilience_score
                    changed = True
                    await ResilienceHistoryService.record_event(
                        existing.resilience_id, "RESILIENCE_SCORE_CHANGED", f"Resilience score updated to {resilience_score}", uow=uow_inst
                    )
                if float(existing.readiness_score) != readiness:
                    existing.readiness_score = readiness
                    changed = True
                    await ResilienceHistoryService.record_event(
                        existing.resilience_id, "READINESS_CHANGED", f"Readiness score updated to {readiness}", uow=uow_inst
                    )
                if float(existing.recovery_confidence_score) != confidence:
                    existing.recovery_confidence_score = confidence
                    changed = True
                    await ResilienceHistoryService.record_event(
                        existing.resilience_id, "RECOVERY_CHANGED", f"Recovery confidence score updated to {confidence}", uow=uow_inst
                    )

                if changed:
                    existing.updated_at = datetime.now(timezone.utc)
                return existing

            # Create new record
            resilience_id = uuid.uuid4()
            
            # Seed standard recovery objectives
            await RecoveryObjectiveService.set_objective(resilience_id, RecoveryObjectiveType.RTO, 4.0, 4.0, uow=uow_inst)
            await RecoveryObjectiveService.set_objective(resilience_id, RecoveryObjectiveType.RPO, 1.0, 1.0, uow=uow_inst)

            obj_comp = await RecoveryObjectiveService.get_resilience_objective_compliance(resilience_id, uow=uow_inst)
            readiness = ResilienceScoringService.calculate_readiness_score(resilience_id, ResilienceStatus.PLANNED)
            confidence = ResilienceScoringService.calculate_recovery_confidence_score(
                resilience_id, ResilienceStatus.PLANNED, obj_comp, readiness
            )
            resilience_score = ResilienceScoringService.calculate_resilience_score(
                resilience_id, ResilienceStatus.PLANNED, service_criticality, readiness, obj_comp
            )

            record = CyberResilienceRecord(
                resilience_id=resilience_id,
                resilience_fingerprint=fingerprint,
                title=title,
                description=description,
                service_name=service_name,
                service_criticality=service_criticality.value if hasattr(service_criticality, 'value') else service_criticality,
                resilience_score=resilience_score,
                readiness_score=readiness,
                recovery_confidence_score=confidence,
                status=ResilienceStatus.PLANNED.value,
                scope_id=scope_id,
                tenant_id=tenant_id
            )

            await uow_inst.resilience_repo.save(record)

            await ResilienceHistoryService.record_event(
                resilience_id, "CREATED", f"Cyber resilience record created: '{title}'", uow=uow_inst
            )
            return record

        if uow:
            return await _sync(uow)
        else:
            async with UnitOfWork() as uow_new:
                record = await _sync(uow_new)
                await uow_new.commit()
                return record

    @classmethod
    async def sync_resilience(cls, db = None) -> List[CyberResilienceRecord]:
        """Continuous sync loop discovering cyber resilience services posture."""
        async with UnitOfWork() as uow:
            rec1 = await cls.create_or_sync_resilience(
                title="Critical Infrastructure Backup",
                description="DR plan validation and recovery backups.",
                service_name="Identity Provider",
                service_criticality=ServiceCriticality.MISSION_CRITICAL,
                uow=uow
            )
            rec2 = await cls.create_or_sync_resilience(
                title="Secondary Active Directory Sync",
                description="Active Directory failover sync validation.",
                service_name="Directory Services",
                service_criticality=ServiceCriticality.HIGH,
                uow=uow
            )
            await uow.commit()
            return [rec1, rec2]

    @classmethod
    async def transition_status(
        cls, resilience_id: uuid.UUID, new_status: ResilienceStatus
    ) -> CyberResilienceRecord:
        """Safely transition report status enforcing forward-only rules and terminal states."""
        async with UnitOfWork() as uow:
            record = await uow.resilience_repo.get(resilience_id)
            if not record:
                raise ValueError(f"Resilience record {resilience_id} not found")

            current_status = ResilienceStatus(record.status)
            if current_status in (ResilienceStatus.COMPLETED, ResilienceStatus.CLOSED):
                # Terminal State Rule
                return record

            allowed = cls.ALLOWED_TRANSITIONS.get(current_status, set())
            if new_status not in allowed:
                raise ValueError(f"Invalid transition from {record.status} to {new_status.value}")

            old_status = current_status
            record.status = new_status.value
            record.updated_at = datetime.now(timezone.utc)

            event_map = {
                ResilienceStatus.ACTIVE: "ACTIVATED",
                ResilienceStatus.VALIDATED: "VALIDATED",
                ResilienceStatus.COMPLETED: "COMPLETED",
                ResilienceStatus.CLOSED: "CLOSED",
            }
            event_type = event_map.get(new_status, "STATUS_CHANGED")

            await ResilienceHistoryService.record_event(
                resilience_id,
                event_type,
                f"Status transitioned from {old_status.value} to {new_status.value}",
                uow=uow
            )
            await uow.commit()
            return record

    @classmethod
    def to_response(cls, record: CyberResilienceRecord) -> CyberResilienceResponse:
        """Convert a CyberResilienceRecord to a CyberResilienceResponse Pydantic schema."""
        return CyberResilienceResponse(
            resilience_id=record.resilience_id,
            resilience_fingerprint=record.resilience_fingerprint,
            title=record.title,
            description=record.description,
            service_name=record.service_name,
            service_criticality=ServiceCriticality(record.service_criticality),
            resilience_score=float(record.resilience_score),
            readiness_score=float(record.readiness_score),
            recovery_confidence_score=float(record.recovery_confidence_score),
            status=ResilienceStatus(record.status),
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
