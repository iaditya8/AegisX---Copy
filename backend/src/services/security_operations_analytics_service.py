import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.security_operations_analytics import (
    AnalyticsStatus,
    AnalyticsResponse,
)
from src.services.analytics_fingerprint_service import AnalyticsFingerprintService
from src.services.analytics_history_service import AnalyticsHistoryService
from src.services.analyst_performance_service import AnalystPerformanceService
from src.services.operational_kpi_service import OperationalKPIService
from src.services.operational_kri_service import OperationalKRIService


class SOCAnalyticsRecord:
    def __init__(
        self,
        analytics_id: uuid.UUID,
        analytics_fingerprint: str,
        analytics_name: str,
        description: str,
        status: AnalyticsStatus,
        scope_id: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.analytics_id = analytics_id
        self.analytics_fingerprint = analytics_fingerprint
        self.analytics_name = analytics_name
        self.description = description
        self.status = status
        self.scope_id = scope_id
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)


class SecurityOperationsAnalyticsService:
    # in-memory store: analytics_id -> SOCAnalyticsRecord
    _analytics: Dict[uuid.UUID, SOCAnalyticsRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    ALLOWED_TRANSITIONS = {
        AnalyticsStatus.ACTIVE: {AnalyticsStatus.REVIEW, AnalyticsStatus.COMPLETED, AnalyticsStatus.ARCHIVED},
        AnalyticsStatus.REVIEW: {AnalyticsStatus.COMPLETED, AnalyticsStatus.ARCHIVED},
        AnalyticsStatus.COMPLETED: {AnalyticsStatus.ARCHIVED},
        AnalyticsStatus.ARCHIVED: set(),  # Terminal
    }

    @classmethod
    def clear_analytics(cls) -> None:
        """Clear all analytics records and lookup cache."""
        cls._analytics.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_analytics(cls) -> List[SOCAnalyticsRecord]:
        """Retrieve all SOC analytics records."""
        return list(cls._analytics.values())

    @classmethod
    def get_analytics(cls, analytics_id: uuid.UUID) -> Optional[SOCAnalyticsRecord]:
        """Retrieve an analytics record by ID."""
        return cls._analytics.get(analytics_id)

    @classmethod
    def get_analytics_by_fingerprint(cls, fingerprint: str) -> Optional[SOCAnalyticsRecord]:
        """Retrieve an analytics record by fingerprint."""
        analytics_id = cls._fingerprint_lookup.get(fingerprint)
        if analytics_id:
            return cls.get_analytics(analytics_id)
        return None

    @classmethod
    async def create_or_sync_analytics(
        cls,
        analytics_name: str,
        description: str,
        scope_id: Optional[uuid.UUID] = None,
    ) -> SOCAnalyticsRecord:
        """Create or synchronize a SOC analytics record based on identity rules."""
        fingerprint = AnalyticsFingerprintService.generate_fingerprint(
            analytics_name, scope_id
        )
        existing = cls.get_analytics_by_fingerprint(fingerprint)

        if existing:
            if existing.status == AnalyticsStatus.ARCHIVED:
                # Terminal State Rule
                return existing

            # COMPLETED protection rule: synchronization cannot move COMPLETED back to ACTIVE
            if existing.status == AnalyticsStatus.COMPLETED:
                return existing

            return existing

        # Create new record
        analytics_id = uuid.uuid4()
        record = SOCAnalyticsRecord(
            analytics_id=analytics_id,
            analytics_fingerprint=fingerprint,
            analytics_name=analytics_name,
            description=description,
            status=AnalyticsStatus.ACTIVE,
            scope_id=scope_id,
        )

        cls._analytics[analytics_id] = record
        cls._fingerprint_lookup[fingerprint] = analytics_id

        AnalyticsHistoryService.record_event(
            analytics_id, "CREATED", f"SOC analytics record created: '{analytics_name}'"
        )
        return record

    @classmethod
    async def sync_analytics(cls, db: AsyncSession) -> List[SOCAnalyticsRecord]:
        """Sync check finding or creating SOC analytics posture records."""
        synced = []
        rec = await cls.create_or_sync_analytics(
            analytics_name="SOC Queue Health Alert Thresholds",
            description="Validates alert thresholds and limits.",
        )
        synced.append(rec)
        return synced

    @classmethod
    def transition_status(
        cls, analytics_id: uuid.UUID, new_status: AnalyticsStatus
    ) -> SOCAnalyticsRecord:
        """Safely transition analytics status enforcing forward-only rules and terminal states."""
        record = cls.get_analytics(analytics_id)
        if not record:
            raise ValueError(f"Analytics record {analytics_id} not found")

        if record.status == AnalyticsStatus.ARCHIVED:
            # Terminal State Rule
            return record

        # COMPLETED state protection: synchronization/worker cannot regress but manual API transitions can move to ARCHIVED
        allowed = cls.ALLOWED_TRANSITIONS.get(record.status, set())
        if new_status not in allowed:
            raise ValueError(f"Invalid transition from {record.status.value} to {new_status.value}")

        old_status = record.status
        record.status = new_status
        record.updated_at = datetime.now(timezone.utc)

        event_map = {
            AnalyticsStatus.REVIEW: "REVIEWED",
            AnalyticsStatus.COMPLETED: "COMPLETED",
            AnalyticsStatus.ARCHIVED: "ARCHIVED",
        }
        event_type = event_map.get(new_status, "STATUS_CHANGED")

        AnalyticsHistoryService.record_event(
            analytics_id,
            event_type,
            f"Status transitioned from {old_status.value} to {new_status.value}",
        )
        return record

    @classmethod
    def to_response(cls, record: SOCAnalyticsRecord) -> AnalyticsResponse:
        return AnalyticsResponse(
            analytics_id=record.analytics_id,
            analytics_fingerprint=record.analytics_fingerprint,
            analytics_name=record.analytics_name,
            description=record.description,
            status=record.status,
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
