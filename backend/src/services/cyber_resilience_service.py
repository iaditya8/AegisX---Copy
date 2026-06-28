import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.cyber_resilience import (
    ResilienceStatus,
    ServiceCriticality,
    CyberResilienceResponse,
)
from src.services.resilience_fingerprint_service import ResilienceFingerprintService
from src.services.resilience_history_service import ResilienceHistoryService
from src.services.recovery_objective_service import RecoveryObjectiveService
from src.services.resilience_scoring_service import ResilienceScoringService


class CyberResilienceRecord:
    def __init__(
        self,
        resilience_id: uuid.UUID,
        resilience_fingerprint: str,
        title: str,
        description: str,
        service_name: str,
        service_criticality: ServiceCriticality,
        resilience_score: float,
        readiness_score: float,
        recovery_confidence_score: float,
        status: ResilienceStatus,
        scope_id: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.resilience_id = resilience_id
        self.resilience_fingerprint = resilience_fingerprint
        self.title = title
        self.description = description
        self.service_name = service_name
        self.service_criticality = service_criticality
        self.resilience_score = resilience_score
        self.readiness_score = readiness_score
        self.recovery_confidence_score = recovery_confidence_score
        self.status = status
        self.scope_id = scope_id
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)


from src.infrastructure.cache.cache_dict import CacheDict


class CyberResilienceService:
    # in-memory store: resilience_id -> CyberResilienceRecord
    _resilience = CacheDict("resilience")
    _fingerprint_lookup = CacheDict("resilience_fingerprints")

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
    def clear_resilience(cls) -> None:
        """Clear all resilience records and lookup cache."""
        cls._resilience.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_resilience(cls) -> List[CyberResilienceRecord]:
        """Retrieve all resilience records."""
        return list(cls._resilience.values())

    @classmethod
    def get_resilience(cls, resilience_id: uuid.UUID) -> Optional[CyberResilienceRecord]:
        """Retrieve a resilience record by ID."""
        return cls._resilience.get(resilience_id)

    @classmethod
    def get_resilience_by_fingerprint(cls, fingerprint: str) -> Optional[CyberResilienceRecord]:
        """Retrieve a resilience record by fingerprint."""
        resilience_id = cls._fingerprint_lookup.get(fingerprint)
        if resilience_id:
            return cls.get_resilience(resilience_id)
        return None

    @classmethod
    async def create_or_sync_resilience(
        cls,
        title: str,
        description: str,
        service_name: str,
        service_criticality: ServiceCriticality,
        scope_id: Optional[uuid.UUID] = None,
    ) -> CyberResilienceRecord:
        """Create or synchronize a cyber resilience record based on identity rules."""
        fingerprint = ResilienceFingerprintService.generate_fingerprint(
            title, service_name, service_criticality.value
        )
        existing = cls.get_resilience_by_fingerprint(fingerprint)

        if existing:
            if existing.status in (ResilienceStatus.COMPLETED, ResilienceStatus.CLOSED):
                # Terminal State Rule
                return existing

            # Calculate scores
            obj_comp = RecoveryObjectiveService.get_resilience_objective_compliance(existing.resilience_id)
            readiness = ResilienceScoringService.calculate_readiness_score(existing.resilience_id, existing.status)
            confidence = ResilienceScoringService.calculate_recovery_confidence_score(
                existing.resilience_id, existing.status, obj_comp, readiness
            )
            resilience = ResilienceScoringService.calculate_resilience_score(
                existing.resilience_id, existing.status, existing.service_criticality, readiness, obj_comp
            )

            changed = False
            if existing.resilience_score != resilience:
                existing.resilience_score = resilience
                changed = True
                ResilienceHistoryService.record_event(
                    existing.resilience_id, "RESILIENCE_SCORE_CHANGED", f"Resilience score updated to {resilience}"
                )
            if existing.readiness_score != readiness:
                existing.readiness_score = readiness
                changed = True
                ResilienceHistoryService.record_event(
                    existing.resilience_id, "READINESS_CHANGED", f"Readiness score updated to {readiness}"
                )
            if existing.recovery_confidence_score != confidence:
                existing.recovery_confidence_score = confidence
                changed = True
                ResilienceHistoryService.record_event(
                    existing.resilience_id, "RECOVERY_CHANGED", f"Recovery confidence score updated to {confidence}"
                )

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
            return existing

        # Create new record
        resilience_id = uuid.uuid4()
        
        # Seed standard recovery objectives
        RecoveryObjectiveService.set_objective(resilience_id, "RTO", 4.0, 4.0)
        RecoveryObjectiveService.set_objective(resilience_id, "RPO", 1.0, 1.0)

        obj_comp = RecoveryObjectiveService.get_resilience_objective_compliance(resilience_id)
        readiness = ResilienceScoringService.calculate_readiness_score(resilience_id, ResilienceStatus.PLANNED)
        confidence = ResilienceScoringService.calculate_recovery_confidence_score(
            resilience_id, ResilienceStatus.PLANNED, obj_comp, readiness
        )
        resilience = ResilienceScoringService.calculate_resilience_score(
            resilience_id, ResilienceStatus.PLANNED, service_criticality, readiness, obj_comp
        )

        record = CyberResilienceRecord(
            resilience_id=resilience_id,
            resilience_fingerprint=fingerprint,
            title=title,
            description=description,
            service_name=service_name,
            service_criticality=service_criticality,
            resilience_score=resilience,
            readiness_score=readiness,
            recovery_confidence_score=confidence,
            status=ResilienceStatus.PLANNED,
            scope_id=scope_id,
        )

        cls._resilience[resilience_id] = record
        cls._fingerprint_lookup[fingerprint] = resilience_id

        ResilienceHistoryService.record_event(
            resilience_id, "CREATED", f"Cyber resilience record created: '{title}'"
        )
        return record

    @classmethod
    async def sync_resilience(cls, db: AsyncSession) -> List[CyberResilienceRecord]:
        """Continuous sync loop discovering cyber resilience services posture."""
        synced = []

        # 1. Critical Infrastructure Backup
        rec1 = await cls.create_or_sync_resilience(
            title="Critical Infrastructure Backup",
            description="DR plan validation and recovery backups.",
            service_name="Identity Provider",
            service_criticality=ServiceCriticality.MISSION_CRITICAL,
        )
        synced.append(rec1)

        # 2. Secondary Active Directory Sync
        rec2 = await cls.create_or_sync_resilience(
            title="Secondary Active Directory Sync",
            description="Active Directory failover sync validation.",
            service_name="Directory Services",
            service_criticality=ServiceCriticality.HIGH,
        )
        synced.append(rec2)

        return synced

    @classmethod
    def transition_status(
        cls, resilience_id: uuid.UUID, new_status: ResilienceStatus
    ) -> CyberResilienceRecord:
        """Safely transition report status enforcing forward-only rules and terminal states."""
        record = cls.get_resilience(resilience_id)
        if not record:
            raise ValueError(f"Resilience record {resilience_id} not found")

        if record.status in (ResilienceStatus.COMPLETED, ResilienceStatus.CLOSED):
            # Terminal State Rule
            return record

        allowed = cls.ALLOWED_TRANSITIONS.get(record.status, set())
        if new_status not in allowed:
            raise ValueError(f"Invalid transition from {record.status.value} to {new_status.value}")

        old_status = record.status
        record.status = new_status
        record.updated_at = datetime.now(timezone.utc)

        event_map = {
            ResilienceStatus.ACTIVE: "ACTIVATED",
            ResilienceStatus.VALIDATED: "VALIDATED",
            ResilienceStatus.COMPLETED: "COMPLETED",
            ResilienceStatus.CLOSED: "CLOSED",
        }
        event_type = event_map.get(new_status, "STATUS_CHANGED")

        ResilienceHistoryService.record_event(
            resilience_id,
            event_type,
            f"Status transitioned from {old_status.value} to {new_status.value}",
        )
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
            service_criticality=record.service_criticality,
            resilience_score=record.resilience_score,
            readiness_score=record.readiness_score,
            recovery_confidence_score=record.recovery_confidence_score,
            status=record.status,
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
