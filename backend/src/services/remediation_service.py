import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.remediation import RemediationHistoryType, RemediationStatus
from src.services.audit_service import create_audit_entry
from src.services.remediation_history_service import RemediationHistoryService
from src.services.remediation_snapshot_service import RemediationSnapshotService
from src.services.sla_monitoring_service import SLAMonitoringService
from src.services.workflow_event_service import WorkflowEventService
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import Remediation as DBRediation, IntelligenceEvent
from src.core.tenant import get_current_tenant_id


class RemediationRecord:
    def __init__(
        self,
        remediation_id: uuid.UUID,
        recommendation_fingerprint: str,
        asset_id: uuid.UUID,
        finding_id: Optional[uuid.UUID],
        status: RemediationStatus,
        due_date: datetime,
        created_at: datetime,
        updated_at: datetime,
        owner: Optional[str] = None,
        reason: Optional[str] = None,
        approved_by: Optional[str] = None,
        exception_approved_at: Optional[datetime] = None,
    ):
        self.remediation_id = remediation_id
        self.recommendation_fingerprint = recommendation_fingerprint
        self.asset_id = asset_id
        self.finding_id = finding_id
        self.status = status
        self.due_date = due_date
        self.created_at = created_at
        self.updated_at = updated_at
        self.owner = owner
        self.reason = reason
        self.approved_by = approved_by
        self.exception_approved_at = exception_approved_at


class RemediationService:
    # Warm L2 cache
    _remediations: Dict[uuid.UUID, RemediationRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def get_all_remediations(cls) -> List[RemediationRecord]:
        """Return all remediation records."""
        return list(cls._remediations.values())

    @classmethod
    def get_remediation(cls, remediation_id: uuid.UUID) -> Optional[RemediationRecord]:
        """Retrieve a specific remediation record."""
        return cls._remediations.get(remediation_id)

    @classmethod
    def get_remediations_by_asset(cls, asset_id: uuid.UUID) -> List[RemediationRecord]:
        """Retrieve all remediation records for an asset."""
        return [r for r in cls._remediations.values() if r.asset_id == asset_id]

    @classmethod
    def clear_remediations(cls) -> None:
        """Clear all in-memory remediation records."""
        cls._remediations.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    async def bootstrap(cls, db: AsyncSession) -> None:
        """Bootstrap the L2 cache from PostgreSQL database."""
        cls.clear_remediations()
        async with UnitOfWork() as uow:
            db_remediations = await uow.remediation_repo.list()
            for db_rem in db_remediations:
                record = RemediationRecord(
                    remediation_id=db_rem.id,
                    recommendation_fingerprint=db_rem.recommendation_fingerprint,
                    asset_id=db_rem.asset_id,
                    finding_id=db_rem.finding_id,
                    status=RemediationStatus(db_rem.status),
                    due_date=db_rem.due_date,
                    created_at=db_rem.created_at,
                    updated_at=db_rem.updated_at,
                    owner=db_rem.owner,
                    reason=db_rem.reason,
                    approved_by=db_rem.approved_by,
                    exception_approved_at=db_rem.exception_approved_at,
                )
                cls._remediations[db_rem.id] = record
                cls._fingerprint_lookup[db_rem.recommendation_fingerprint] = db_rem.id

    @classmethod
    def validate_transition(
        cls, old_status: RemediationStatus, new_status: RemediationStatus
    ) -> None:
        """Enforce strict state machine transitions."""
        if old_status == new_status:
            return

        if old_status in [
            RemediationStatus.REMEDIATED,
            RemediationStatus.FALSE_POSITIVE,
            RemediationStatus.ACCEPTED_RISK,
        ]:
            raise ValueError(
                f"Cannot transition from terminal state {old_status.value}"
            )

        if old_status == RemediationStatus.OPEN:
            if new_status not in [
                RemediationStatus.IN_PROGRESS,
                RemediationStatus.ACCEPTED_RISK,
                RemediationStatus.FALSE_POSITIVE,
                RemediationStatus.DEFERRED,
            ]:
                raise ValueError(
                    f"Invalid transition from {old_status.value} to {new_status.value}"
                )

        elif old_status == RemediationStatus.IN_PROGRESS:
            if new_status not in [
                RemediationStatus.REMEDIATED,
                RemediationStatus.ACCEPTED_RISK,
                RemediationStatus.DEFERRED,
            ]:
                raise ValueError(
                    f"Invalid transition from {old_status.value} to {new_status.value}"
                )

        elif old_status == RemediationStatus.DEFERRED:
            if new_status not in [
                RemediationStatus.IN_PROGRESS,
                RemediationStatus.ACCEPTED_RISK,
            ]:
                raise ValueError(
                    f"Invalid transition from {old_status.value} to {new_status.value}"
                )

    @classmethod
    async def sync_recommendation(
        cls,
        db: AsyncSession,
        fingerprint: str,
        asset_id: uuid.UUID,
        finding_id: Optional[uuid.UUID],
        priority: str,
        title: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> RemediationRecord:
        """Create OPEN remediation if recommendation is new, else sync it."""
        now = datetime.now(timezone.utc)
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        if fingerprint in cls._fingerprint_lookup:
            rem_id = cls._fingerprint_lookup[fingerprint]
            record = cls._remediations[rem_id]

            record.due_date = SLAMonitoringService.calculate_due_date(
                record.created_at, priority
            )
            record.updated_at = now

            async with UnitOfWork() as uow:
                db_rem = await uow.remediation_repo.get(rem_id)
                if db_rem:
                    db_rem.due_date = record.due_date
                    db_rem.updated_at = now
                    db_rem.updated_by = actor_id
                    await uow.commit()

            RemediationSnapshotService.update_snapshot(asset_id)
            return record

        # Create new record
        rem_id = uuid.uuid4()
        due_date = SLAMonitoringService.calculate_due_date(now, priority)

        record = RemediationRecord(
            remediation_id=rem_id,
            recommendation_fingerprint=fingerprint,
            asset_id=asset_id,
            finding_id=finding_id,
            status=RemediationStatus.OPEN,
            due_date=due_date,
            created_at=now,
            updated_at=now,
        )

        cls._remediations[rem_id] = record
        cls._fingerprint_lookup[fingerprint] = rem_id

        async with UnitOfWork() as uow:
            db_rem = DBRediation(
                tenant_id=tenant_id,
                id=rem_id,
                recommendation_fingerprint=fingerprint,
                asset_id=asset_id,
                finding_id=finding_id,
                status=RemediationStatus.OPEN.value,
                due_date=due_date,
                created_at=now,
                updated_at=now,
            )
            await uow.remediation_repo.save(db_rem)

            # Log history
            await RemediationHistoryService.record_event(
                remediation_id=rem_id,
                history_type=RemediationHistoryType.CREATED,
                new_value={"status": record.status.value, "title": title},
                actor_id=actor_id,
                uow=uow,
            )

            # Stage outbox event
            outbox_evt = IntelligenceEvent(
                tenant_id=tenant_id,
                event_type="remediation.created",
                payload={
                    "remediation_id": str(rem_id),
                    "recommendation_fingerprint": fingerprint,
                    "asset_id": str(asset_id),
                    "status": record.status.value,
                }
            )
            uow.session.add(outbox_evt)
            await uow.commit()

        # Emit workflow event
        await WorkflowEventService.emit_event(
            db=db,
            event_type="remediation.created",
            payload={
                "remediation_id": str(rem_id),
                "recommendation_fingerprint": fingerprint,
                "asset_id": str(asset_id),
                "status": record.status.value,
            },
        )

        # Audit Entry
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="remediation.created",
            target_type="remediation",
            target_id=rem_id,
            metadata={
                "remediation_id": str(rem_id),
                "status": record.status.value,
                "recommendation_fingerprint": fingerprint,
            },
        )

        RemediationSnapshotService.update_snapshot(asset_id)
        return record

    @classmethod
    async def update_status(
        cls,
        db: AsyncSession,
        remediation_id: uuid.UUID,
        status: RemediationStatus,
        actor_id: Optional[uuid.UUID] = None,
        reason: Optional[str] = None,
        approved_by: Optional[str] = None,
        bypass_terminal: bool = False,
    ) -> RemediationRecord:
        """Update status of a remediation record with strict transition validation."""
        record = cls.get_remediation(remediation_id)
        if not record:
            raise ValueError(f"Remediation {remediation_id} not found")

        if not bypass_terminal:
            if status in [
                RemediationStatus.ACCEPTED_RISK,
                RemediationStatus.FALSE_POSITIVE,
                RemediationStatus.DEFERRED,
            ]:
                if not reason or not approved_by:
                    raise ValueError(
                        "Reason and approved_by required for exception status"
                    )
                from src.services.exception_service import ExceptionService

                await ExceptionService.apply_exception(
                    db, record, status, reason, approved_by, actor_id
                )
                return record

            cls.validate_transition(record.status, status)
            
        old_status = record.status
        record.status = status
        record.updated_at = datetime.now(timezone.utc)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_rem = await uow.remediation_repo.get(remediation_id)
            if db_rem:
                db_rem.status = status.value
                db_rem.updated_at = record.updated_at
                db_rem.updated_by = actor_id

                # Log history
                await RemediationHistoryService.record_event(
                    remediation_id=remediation_id,
                    history_type=RemediationHistoryType.STATUS_CHANGE,
                    old_value={"status": old_status.value},
                    new_value={"status": status.value},
                    actor_id=actor_id,
                    uow=uow,
                )

                # Stage outbox event
                event_name = (
                    "remediation.started"
                    if status == RemediationStatus.IN_PROGRESS
                    else "remediation.completed"
                )
                outbox_evt = IntelligenceEvent(
                    tenant_id=tenant_id,
                    event_type=event_name,
                    payload={
                        "remediation_id": str(remediation_id),
                        "status": status.value,
                    }
                )
                uow.session.add(outbox_evt)
                await uow.commit()

        # Emit events and audits
        event_name = (
            "remediation.started"
            if status == RemediationStatus.IN_PROGRESS
            else "remediation.completed"
        )
        await WorkflowEventService.emit_event(
            db=db,
            event_type=event_name,
            payload={
                "remediation_id": str(remediation_id),
                "status": status.value,
            },
        )

        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action=event_name,
            target_type="remediation",
            target_id=remediation_id,
            metadata={
                "remediation_id": str(remediation_id),
                "status": status.value,
            },
        )

        RemediationSnapshotService.update_snapshot(record.asset_id)
        return record

    @classmethod
    async def assign_owner(
        cls,
        db: AsyncSession,
        remediation_id: uuid.UUID,
        owner: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> RemediationRecord:
        """Assign owner to a remediation record."""
        record = cls.get_remediation(remediation_id)
        if not record:
            raise ValueError(f"Remediation {remediation_id} not found")

        old_owner = record.owner
        record.owner = owner
        record.updated_at = datetime.now(timezone.utc)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_rem = await uow.remediation_repo.get(remediation_id)
            if db_rem:
                db_rem.owner = owner
                db_rem.updated_at = record.updated_at
                db_rem.updated_by = actor_id

                # Log history
                await RemediationHistoryService.record_event(
                    remediation_id=remediation_id,
                    history_type=RemediationHistoryType.OWNER_CHANGE,
                    old_value={"owner": old_owner},
                    new_value={"owner": owner},
                    actor_id=actor_id,
                    uow=uow,
                )

                # Stage outbox event
                event_name = (
                    "remediation.assigned" if old_owner is None else "remediation.reassigned"
                )
                outbox_evt = IntelligenceEvent(
                    tenant_id=tenant_id,
                    event_type=event_name,
                    payload={
                        "remediation_id": str(remediation_id),
                        "old_owner": old_owner,
                        "new_owner": owner,
                    }
                )
                uow.session.add(outbox_evt)
                await uow.commit()

        # Emit events
        event_name = (
            "remediation.assigned" if old_owner is None else "remediation.reassigned"
        )
        await WorkflowEventService.emit_event(
            db=db,
            event_type=event_name,
            payload={
                "remediation_id": str(remediation_id),
                "old_owner": old_owner,
                "new_owner": owner,
            },
        )

        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action=event_name,
            target_type="remediation",
            target_id=remediation_id,
            metadata={
                "remediation_id": str(remediation_id),
                "old_owner": old_owner,
                "new_owner": owner,
            },
        )

        return record
