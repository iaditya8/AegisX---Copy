import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.security_knowledge import (
    KnowledgeStatus,
    KnowledgeType,
    KnowledgeRecordResponse,
)
from src.services.knowledge_fingerprint_service import KnowledgeFingerprintService
from src.services.knowledge_history_service import KnowledgeHistoryService
from src.services.knowledge_relevance_service import KnowledgeRelevanceService
from src.services.knowledge_tag_registry import KnowledgeTagRegistry
from src.services.knowledge_relationship_service import KnowledgeRelationshipService
from src.services.knowledge_recommendation_service import KnowledgeRecommendationService


class KnowledgeRecord:
    def __init__(
        self,
        knowledge_id: uuid.UUID,
        knowledge_fingerprint: str,
        knowledge_type: KnowledgeType,
        title: str,
        content: str,
        relevance_score: float,
        confidence_score: float,
        status: KnowledgeStatus,
        tags: List[str],
        scope_id: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.knowledge_id = knowledge_id
        self.knowledge_fingerprint = knowledge_fingerprint
        self.knowledge_type = knowledge_type
        self.title = title
        self.content = content
        self.relevance_score = relevance_score
        self.confidence_score = confidence_score
        self.status = status
        self.tags = tags
        self.scope_id = scope_id
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)


from src.infrastructure.cache.cache_dict import CacheDict


class SecurityKnowledgeService:
    # in-memory store: knowledge_id -> KnowledgeRecord
    _knowledge = CacheDict("security_knowledge")
    _fingerprint_lookup = CacheDict("security_knowledge_fingerprints")

    ALLOWED_TRANSITIONS = {
        KnowledgeStatus.ACTIVE: {
            KnowledgeStatus.REVIEW,
            KnowledgeStatus.APPROVED,
            KnowledgeStatus.ARCHIVED,
        },
        KnowledgeStatus.REVIEW: {
            KnowledgeStatus.APPROVED,
            KnowledgeStatus.ARCHIVED,
        },
        KnowledgeStatus.APPROVED: {KnowledgeStatus.ARCHIVED},
        KnowledgeStatus.ARCHIVED: set(),  # Terminal
    }

    @classmethod
    def clear_knowledge(cls) -> None:
        """Clear all GRC knowledge records and lookup cache."""
        cls._knowledge.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_knowledge(cls) -> List[KnowledgeRecord]:
        """Retrieve all GRC knowledge records."""
        return list(cls._knowledge.values())

    @classmethod
    def get_knowledge(cls, knowledge_id: uuid.UUID) -> Optional[KnowledgeRecord]:
        """Retrieve a GRC knowledge record by ID."""
        return cls._knowledge.get(knowledge_id)

    @classmethod
    def get_knowledge_by_fingerprint(cls, fingerprint: str) -> Optional[KnowledgeRecord]:
        """Retrieve a GRC knowledge record by fingerprint."""
        knowledge_id = cls._fingerprint_lookup.get(fingerprint)
        if knowledge_id:
            return cls.get_knowledge(knowledge_id)
        return None

    @classmethod
    async def create_or_sync_knowledge(
        cls,
        title: str,
        content: str,
        knowledge_type: KnowledgeType,
        tags: List[str],
        scope_id: Optional[uuid.UUID] = None,
    ) -> KnowledgeRecord:
        """Create or synchronize GRC knowledge record enforcing identity rules."""
        fingerprint = KnowledgeFingerprintService.generate_fingerprint(
            knowledge_type.value, title, scope_id
        )
        existing = cls.get_knowledge_by_fingerprint(fingerprint)

        # Validate tags against the tag registry
        valid_tags = [t for t in tags if KnowledgeTagRegistry.validate(t)]

        # Calculate metrics
        relevance = KnowledgeRelevanceService.calculate_relevance(title, content)
        confidence = KnowledgeRelevanceService.calculate_confidence(
            existing.status == KnowledgeStatus.APPROVED if existing else False
        )

        if existing:
            if existing.status == KnowledgeStatus.ARCHIVED:
                # Terminal State Rule
                return existing

            changed = False
            if existing.content != content:
                existing.content = content
                changed = True
            if existing.relevance_score != relevance:
                existing.relevance_score = relevance
                changed = True
                KnowledgeHistoryService.record_event(
                    existing.knowledge_id, "SCORE_CHANGED", f"Relevance score updated to {relevance}"
                )
            if existing.confidence_score != confidence:
                existing.confidence_score = confidence
                changed = True

            # Sync tags (preserve existing but append new valid ones)
            for t in valid_tags:
                if t not in existing.tags:
                    existing.tags.append(t)
                    changed = True

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
            return existing

        # Create new record
        knowledge_id = uuid.uuid4()

        record = KnowledgeRecord(
            knowledge_id=knowledge_id,
            knowledge_fingerprint=fingerprint,
            knowledge_type=knowledge_type,
            title=title,
            content=content,
            relevance_score=relevance,
            confidence_score=confidence,
            status=KnowledgeStatus.ACTIVE,
            tags=valid_tags,
            scope_id=scope_id,
        )

        cls._knowledge[knowledge_id] = record
        cls._fingerprint_lookup[fingerprint] = knowledge_id

        # Pre-seed relationships and recommendations in services
        KnowledgeRelationshipService.add_relationship(
            knowledge_id, "knowledge", uuid.uuid4(), "detection", "MAPPED"
        )
        KnowledgeRecommendationService.get_recommendations(knowledge_id, title)

        KnowledgeHistoryService.record_event(
            knowledge_id, "CREATED", f"Knowledge record created: '{title}'"
        )
        return record

    @classmethod
    async def add_tag(cls, knowledge_id: uuid.UUID, tag: str) -> None:
        """Add tag to knowledge record, validating it first."""
        record = cls.get_knowledge(knowledge_id)
        if not record:
            raise ValueError(f"Knowledge record {knowledge_id} not found")

        if record.status == KnowledgeStatus.ARCHIVED:
            raise ValueError("Cannot modify tags of an archived knowledge record")

        if not KnowledgeTagRegistry.validate(tag):
            raise ValueError(f"Invalid tag '{tag}'")

        if tag not in record.tags:
            record.tags.append(tag)
            record.updated_at = datetime.now(timezone.utc)
            KnowledgeHistoryService.record_event(
                knowledge_id, "TAG_ADDED", f"Tag '{tag}' added."
            )

    @classmethod
    async def sync_knowledge(cls, db: AsyncSession) -> List[KnowledgeRecord]:
        """Continuous sync loop GRC knowledge bases."""
        synced = []

        # 1. phishing mitigation playbook
        rec1 = await cls.create_or_sync_knowledge(
            title="phishing mitigation playbook",
            content="Standard guidelines for phishing incidents.",
            knowledge_type=KnowledgeType.PLAYBOOK,
            tags=["phishing", "incident_response"],
        )
        synced.append(rec1)

        # 2. ransomware forensics investigation
        rec2 = await cls.create_or_sync_knowledge(
            title="ransomware forensics investigation",
            content="Ransomware decryption recovery steps.",
            knowledge_type=KnowledgeType.FORENSICS,
            tags=["ransomware", "forensics"],
        )
        synced.append(rec2)

        return synced

    @classmethod
    def transition_status(
        cls, knowledge_id: uuid.UUID, new_status: KnowledgeStatus
    ) -> KnowledgeRecord:
        """Safely transition GRC knowledge status enforcing forward-only rules and terminal states."""
        record = cls.get_knowledge(knowledge_id)
        if not record:
            raise ValueError(f"Knowledge record {knowledge_id} not found")

        if record.status == KnowledgeStatus.ARCHIVED:
            # Terminal State Rule
            return record

        allowed = cls.ALLOWED_TRANSITIONS.get(record.status, set())
        if new_status not in allowed:
            raise ValueError(f"Invalid transition from {record.status.value} to {new_status.value}")

        old_status = record.status
        record.status = new_status
        record.updated_at = datetime.now(timezone.utc)

        # Recalculate confidence if approved
        if new_status == KnowledgeStatus.APPROVED:
            record.confidence_score = KnowledgeRelevanceService.calculate_confidence(True)

        event_map = {
            KnowledgeStatus.REVIEW: "REVIEW",
            KnowledgeStatus.APPROVED: "APPROVED",
            KnowledgeStatus.ARCHIVED: "ARCHIVED",
        }
        event_type = event_map.get(new_status, "STATUS_CHANGED")

        KnowledgeHistoryService.record_event(
            knowledge_id,
            event_type,
            f"Status transitioned from {old_status.value} to {new_status.value}",
        )
        return record

    @classmethod
    def recalculate_knowledge(cls) -> None:
        """Recalculate GRC knowledge scores and statuses deterministically (derived intelligence)."""
        from src.services.knowledge_severity_registry import KnowledgeSeverityRegistry

        for record in cls.get_all_knowledge():
            if record.status == KnowledgeStatus.ARCHIVED:
                continue

            old_relevance = record.relevance_score
            old_confidence = record.confidence_score
            old_severity = KnowledgeSeverityRegistry.determine_severity(old_relevance)

            # Recalculate
            new_relevance = KnowledgeRelevanceService.calculate_relevance(record.title, record.content)
            new_confidence = KnowledgeRelevanceService.calculate_confidence(record.status == KnowledgeStatus.APPROVED)
            new_severity = KnowledgeSeverityRegistry.determine_severity(new_relevance)

            changed = False
            if record.relevance_score != new_relevance:
                record.relevance_score = new_relevance
                changed = True
                KnowledgeHistoryService.record_event(
                    record.knowledge_id, "RELEVANCE_CHANGED", f"Relevance score updated from {old_relevance} to {new_relevance}"
                )

            if record.confidence_score != new_confidence:
                record.confidence_score = new_confidence
                changed = True
                KnowledgeHistoryService.record_event(
                    record.knowledge_id, "CONFIDENCE_CHANGED", f"Confidence score updated from {old_confidence} to {new_confidence}"
                )

            if old_severity != new_severity:
                changed = True
                KnowledgeHistoryService.record_event(
                    record.knowledge_id, "SEVERITY_CHANGED", f"Severity level updated from {old_severity} to {new_severity}"
                )

            if changed:
                record.updated_at = datetime.now(timezone.utc)

    @classmethod
    def to_response(cls, record: KnowledgeRecord) -> KnowledgeRecordResponse:
        return KnowledgeRecordResponse(
            knowledge_id=record.knowledge_id,
            knowledge_fingerprint=record.knowledge_fingerprint,
            knowledge_type=record.knowledge_type,
            title=record.title,
            content=record.content,
            relevance_score=record.relevance_score,
            confidence_score=record.confidence_score,
            status=record.status,
            tags=record.tags,
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
