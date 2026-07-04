from typing import List, Optional
import uuid
from datetime import datetime, timezone
from sqlalchemy.future import select
from src.core.tenant import get_current_tenant_id
from src.domain.entities.security_operations_analytics import (
    AnalyticsStatus,
    AnalyticsResponse,
)
from src.infrastructure.database.models import SOCAnalyticsRecord
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.services.analytics_fingerprint_service import AnalyticsFingerprintService
from src.services.analytics_history_service import AnalyticsHistoryService


class SecurityOperationsAnalyticsService:
    ALLOWED_TRANSITIONS = {
        AnalyticsStatus.ACTIVE: {AnalyticsStatus.REVIEW, AnalyticsStatus.COMPLETED, AnalyticsStatus.ARCHIVED},
        AnalyticsStatus.REVIEW: {AnalyticsStatus.COMPLETED, AnalyticsStatus.ARCHIVED},
        AnalyticsStatus.COMPLETED: {AnalyticsStatus.ARCHIVED},
        AnalyticsStatus.ARCHIVED: set(),  # Terminal
    }

    @classmethod
    async def clear_analytics(cls) -> None:
        """Clear all analytics records."""
        pass

    @classmethod
    async def get_all_analytics(cls) -> List[SOCAnalyticsRecord]:
        """Retrieve all SOC analytics records."""
        async with UnitOfWork() as uow:
            return await uow.soc_repo.list()

    @classmethod
    async def get_analytics(cls, analytics_id: uuid.UUID) -> Optional[SOCAnalyticsRecord]:
        """Retrieve an analytics record by ID."""
        async with UnitOfWork() as uow:
            return await uow.soc_repo.get(analytics_id)

    @classmethod
    async def get_analytics_by_fingerprint(cls, fingerprint: str, uow: Optional[UnitOfWork] = None) -> Optional[SOCAnalyticsRecord]:
        """Retrieve an analytics record by fingerprint."""
        async def _get(uow_inst: UnitOfWork) -> Optional[SOCAnalyticsRecord]:
            stmt = select(SOCAnalyticsRecord).filter_by(analytics_fingerprint=fingerprint)
            res = await uow_inst.session.execute(stmt)
            return res.scalar_one_or_none()

        if uow:
            return await _get(uow)
        else:
            async with UnitOfWork() as uow_new:
                return await _get(uow_new)

    @classmethod
    async def create_or_sync_analytics(
        cls,
        analytics_name: str,
        description: str,
        scope_id: Optional[uuid.UUID] = None,
        uow: Optional[UnitOfWork] = None,
    ) -> SOCAnalyticsRecord:
        """Create or synchronize a SOC analytics record based on identity rules."""
        fingerprint = AnalyticsFingerprintService.generate_fingerprint(
            analytics_name, scope_id
        )
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        async def _sync(uow_inst: UnitOfWork) -> SOCAnalyticsRecord:
            existing = await cls.get_analytics_by_fingerprint(fingerprint, uow=uow_inst)
            if existing:
                if existing.status == AnalyticsStatus.ARCHIVED.value:
                    # Terminal State Rule
                    return existing

                # COMPLETED protection rule: synchronization cannot move COMPLETED back to ACTIVE
                if existing.status == AnalyticsStatus.COMPLETED.value:
                    return existing

                return existing

            # Create new record
            analytics_id = uuid.uuid4()
            record = SOCAnalyticsRecord(
                analytics_id=analytics_id,
                analytics_fingerprint=fingerprint,
                analytics_name=analytics_name,
                description=description,
                status=AnalyticsStatus.ACTIVE.value,
                scope_id=scope_id,
                tenant_id=tenant_id
            )

            await uow_inst.soc_repo.save(record)

            await AnalyticsHistoryService.record_event(
                analytics_id, "CREATED", f"SOC analytics record created: '{analytics_name}'", uow=uow_inst
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
    async def sync_analytics(cls, db = None) -> List[SOCAnalyticsRecord]:
        """Sync check finding or creating SOC analytics posture records."""
        async with UnitOfWork() as uow:
            rec = await cls.create_or_sync_analytics(
                analytics_name="SOC Queue Health Alert Thresholds",
                description="Validates alert thresholds and limits.",
                uow=uow
            )
            await uow.commit()
            return [rec]

    @classmethod
    async def transition_status(
        cls, analytics_id: uuid.UUID, new_status: AnalyticsStatus
    ) -> SOCAnalyticsRecord:
        """Safely transition analytics status enforcing forward-only rules and terminal states."""
        async with UnitOfWork() as uow:
            record = await uow.soc_repo.get(analytics_id)
            if not record:
                raise ValueError(f"Analytics record {analytics_id} not found")

            current_status = AnalyticsStatus(record.status)
            if current_status == AnalyticsStatus.ARCHIVED:
                # Terminal State Rule
                return record

            # COMPLETED state protection: synchronization/worker cannot regress but manual API transitions can move to ARCHIVED
            allowed = cls.ALLOWED_TRANSITIONS.get(current_status, set())
            if new_status not in allowed:
                raise ValueError(f"Invalid transition from {record.status} to {new_status.value}")

            old_status = current_status
            record.status = new_status.value
            record.updated_at = datetime.now(timezone.utc)

            event_map = {
                AnalyticsStatus.REVIEW: "REVIEWED",
                AnalyticsStatus.COMPLETED: "COMPLETED",
                AnalyticsStatus.ARCHIVED: "ARCHIVED",
            }
            event_type = event_map.get(new_status, "STATUS_CHANGED")

            await AnalyticsHistoryService.record_event(
                analytics_id,
                event_type,
                f"Status transitioned from {old_status.value} to {new_status.value}",
                uow=uow
            )
            await uow.commit()
            return record

    @classmethod
    def to_response(cls, record: SOCAnalyticsRecord) -> AnalyticsResponse:
        return AnalyticsResponse(
            analytics_id=record.analytics_id,
            analytics_fingerprint=record.analytics_fingerprint,
            analytics_name=record.analytics_name,
            description=record.description,
            status=AnalyticsStatus(record.status),
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
