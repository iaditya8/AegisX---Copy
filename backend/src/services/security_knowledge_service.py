import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.tenant import get_current_tenant_id
from src.domain.entities.security_knowledge import (
    KnowledgeStatus,
    KnowledgeType,
    KnowledgeRecordResponse,
)
from src.infrastructure.database.models import SecurityKnowledgeRecord, SecurityKnowledgeRelationship, SecurityKnowledgeRecommendation, SecurityKnowledgeHistory, IntelligenceEvent, AuditLog
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.services.knowledge_fingerprint_service import KnowledgeFingerprintService
from src.services.knowledge_history_service import KnowledgeHistoryService
from src.services.knowledge_relevance_service import KnowledgeRelevanceService
from src.services.knowledge_tag_registry import KnowledgeTagRegistry
from src.services.knowledge_relationship_service import KnowledgeRelationshipService
from src.services.knowledge_recommendation_service import KnowledgeRecommendationService
from src.infrastructure.cache.cache_dict import CacheDict


class SecurityKnowledgeService:
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
    async def get_all_knowledge(cls) -> List[SecurityKnowledgeRecord]:
        """Retrieve all GRC knowledge records."""
        async with UnitOfWork() as uow:
            # We want to read active (not soft deleted) knowledge records
            # Wait, there's no filter_by tenant since knowledge might be shared or tenant specific.
            # But the repository already isolates by tenant in tenant_isolation RLS and get_by_id checks.
            # Let's retrieve all knowledge records for the tenant
            tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
            records = await uow.knowledge_repo.list() # list returns all matching tenant
            # filter out is_deleted
            active_records = [r for r in records if not r.is_deleted]
            for r in active_records:
                cls._knowledge[r.id] = r
                cls._fingerprint_lookup[r.knowledge_fingerprint] = r.id
            return active_records

    @classmethod
    async def get_knowledge(cls, knowledge_id: uuid.UUID) -> Optional[SecurityKnowledgeRecord]:
        """Retrieve a GRC knowledge record by ID."""
        cached = cls._knowledge.get(knowledge_id)
        if cached:
            return cached
        async with UnitOfWork() as uow:
            record = await uow.knowledge_repo.get_by_id(knowledge_id)
            if record:
                cls._knowledge[record.id] = record
                cls._fingerprint_lookup[record.knowledge_fingerprint] = record.id
                return record
        return None

    @classmethod
    async def get_knowledge_by_fingerprint(cls, fingerprint: str) -> Optional[SecurityKnowledgeRecord]:
        """Retrieve a GRC knowledge record by fingerprint."""
        knowledge_id = cls._fingerprint_lookup.get(fingerprint)
        if knowledge_id:
            cached = cls._knowledge.get(knowledge_id)
            if cached:
                return cached
        async with UnitOfWork() as uow:
            tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
            record = await uow.knowledge_repo.get_by_fingerprint(tenant_id, fingerprint)
            if record:
                cls._knowledge[record.id] = record
                cls._fingerprint_lookup[record.knowledge_fingerprint] = record.id
                return record
        return None

    @classmethod
    async def create_or_sync_knowledge(
        cls,
        title: str,
        content: str,
        knowledge_type: KnowledgeType,
        tags: List[str],
        scope_id: Optional[uuid.UUID] = None,
        uow: Optional[UnitOfWork] = None,
    ) -> SecurityKnowledgeRecord:
        """Create or synchronize GRC knowledge record enforcing identity rules."""
        fingerprint = KnowledgeFingerprintService.generate_fingerprint(
            knowledge_type.value, title, scope_id
        )
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        # Validate tags against the tag registry
        valid_tags = [t for t in tags if KnowledgeTagRegistry.validate(t)]

        # Calculate metrics
        relevance = KnowledgeRelevanceService.calculate_relevance(title, content)
        
        async def _sync(uow_inst: UnitOfWork) -> SecurityKnowledgeRecord:
            existing = await uow_inst.knowledge_repo.get_by_fingerprint(tenant_id, fingerprint)
            confidence = KnowledgeRelevanceService.calculate_confidence(
                existing.status == KnowledgeStatus.APPROVED.value if existing else False
            )

            if existing:
                if existing.status == KnowledgeStatus.ARCHIVED.value:
                    return existing

                changed = False
                if existing.content_markdown != content:
                    existing.content_markdown = content
                    # update summary
                    existing.content_summary = content[:200] + "..." if len(content) > 200 else content
                    changed = True
                if float(existing.relevance_score) != relevance:
                    existing.relevance_score = relevance
                    changed = True
                    # Record history
                    hist = SecurityKnowledgeHistory(
                        knowledge_id=existing.id,
                        event_type="SCORE_CHANGED",
                        details=f"Relevance score updated to {relevance}",
                        tenant_id=tenant_id
                    )
                    uow_inst.session.add(hist)
                if float(existing.confidence_score) != confidence:
                    existing.confidence_score = confidence
                    changed = True

                # Sync tags
                for t in valid_tags:
                    if t not in existing.tags:
                        existing.tags.append(t)
                        changed = True

                if changed:
                    existing.updated_at = datetime.now(timezone.utc)
                    existing.version += 1
                    
                    event = IntelligenceEvent(
                        tenant_id=tenant_id,
                        domain="knowledge",
                        entity_id=existing.id,
                        event_type="knowledge.updated",
                        payload={"id": str(existing.id), "title": existing.title, "relevance_score": float(existing.relevance_score)},
                        status="pending"
                    )
                    uow_inst.session.add(event)
                    
                    audit = AuditLog(
                        tenant_id=tenant_id,
                        actor_id=existing.created_by,
                        action="update_knowledge",
                        target_type="knowledge",
                        target_id=existing.id,
                        metadata_json={"title": existing.title},
                        timestamp=datetime.now(timezone.utc)
                    )
                    uow_inst.session.add(audit)

                return existing

            # Create new record
            summary = content[:200] + "..." if len(content) > 200 else content
            record = SecurityKnowledgeRecord(
                knowledge_fingerprint=fingerprint,
                knowledge_type=knowledge_type.value,
                title=title,
                content_markdown=content,
                content_summary=summary,
                relevance_score=relevance,
                confidence_score=confidence,
                status=KnowledgeStatus.ACTIVE.value,
                tags=valid_tags,
                scope_id=scope_id,
                tenant_id=tenant_id,
                version=1
            )
            await uow_inst.knowledge_repo.save(record)
            await uow_inst.session.flush()

            # Pre-seed relationships and recommendations in services
            await KnowledgeRelationshipService.add_relationship(
                record.id, "knowledge", uuid.uuid4(), "detection", "MAPPED", uow=uow_inst
            )
            
            # Seed recommendation
            rec_list = KnowledgeRecommendationService.get_recommendations(record.id, title)
            for i, item in enumerate(rec_list):
                db_rec = SecurityKnowledgeRecommendation(
                    knowledge_id=record.id,
                    title=item.title if hasattr(item, 'title') else "Mock Recommendation",
                    description=item.description if hasattr(item, 'description') else "Details...",
                    rank=i + 1,
                    tenant_id=tenant_id,
                    version=1
                )
                await uow_inst.knowledge_repo.save_recommendation(db_rec)

            # Record history
            hist = SecurityKnowledgeHistory(
                knowledge_id=record.id,
                event_type="CREATED",
                details=f"Knowledge record created: '{title}'",
                tenant_id=tenant_id
            )
            uow_inst.session.add(hist)

            # Outbox Event
            event = IntelligenceEvent(
                tenant_id=tenant_id,
                domain="knowledge",
                entity_id=record.id,
                event_type="knowledge.created",
                payload={"id": str(record.id), "title": record.title, "relevance_score": float(record.relevance_score)},
                status="pending"
            )
            uow_inst.session.add(event)

            # Audit Log
            audit = AuditLog(
                tenant_id=tenant_id,
                actor_id=None,
                action="create_knowledge",
                target_type="knowledge",
                target_id=record.id,
                metadata_json={"title": record.title},
                timestamp=datetime.now(timezone.utc)
            )
            uow_inst.session.add(audit)

            return record

        if uow:
            rec = await _sync(uow)
            cls._knowledge[rec.id] = rec
            cls._fingerprint_lookup[rec.knowledge_fingerprint] = rec.id
            return rec
        else:
            async with UnitOfWork() as new_uow:
                rec = await _sync(new_uow)
                await new_uow.commit()
                cls._knowledge[rec.id] = rec
                cls._fingerprint_lookup[rec.knowledge_fingerprint] = rec.id
                return rec

    @classmethod
    async def add_tag(cls, knowledge_id: uuid.UUID, tag: str) -> None:
        """Add tag to knowledge record, validating it first."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            record = await uow.knowledge_repo.get_by_id(knowledge_id)
            if not record:
                raise ValueError(f"Knowledge record {knowledge_id} not found")

            if record.status == KnowledgeStatus.ARCHIVED.value:
                raise ValueError("Cannot modify tags of an archived knowledge record")

            if not KnowledgeTagRegistry.validate(tag):
                raise ValueError(f"Invalid tag '{tag}'")

            # copy tags to avoid mutating in-place if SQLAlchemy array type
            tags_list = list(record.tags)
            if tag not in tags_list:
                tags_list.append(tag)
                record.tags = tags_list
                record.updated_at = datetime.now(timezone.utc)
                record.version += 1

                # Record history
                hist = SecurityKnowledgeHistory(
                    knowledge_id=knowledge_id,
                    event_type="TAG_ADDED",
                    details=f"Tag '{tag}' added.",
                    tenant_id=tenant_id
                )
                uow.session.add(hist)

                # Outbox Event
                event = IntelligenceEvent(
                    tenant_id=tenant_id,
                    domain="knowledge",
                    entity_id=knowledge_id,
                    event_type="knowledge.updated",
                    payload={"id": str(knowledge_id), "tags": record.tags},
                    status="pending"
                )
                uow.session.add(event)

                # Audit Log
                audit = AuditLog(
                    tenant_id=tenant_id,
                    actor_id=record.created_by,
                    action="add_tag_knowledge",
                    target_type="knowledge",
                    target_id=knowledge_id,
                    metadata_json={"tag": tag},
                    timestamp=datetime.now(timezone.utc)
                )
                uow.session.add(audit)

                await uow.commit()

                # Refresh cache
                cls._knowledge[record.id] = record
                cls._fingerprint_lookup[record.knowledge_fingerprint] = record.id

    @classmethod
    async def sync_knowledge(cls, db: AsyncSession) -> List[SecurityKnowledgeRecord]:
        """Continuous sync loop GRC knowledge bases."""
        synced = []
        async with UnitOfWork() as uow:
            rec1 = await cls.create_or_sync_knowledge(
                title="phishing mitigation playbook",
                content="Standard guidelines for phishing incidents.",
                knowledge_type=KnowledgeType.PLAYBOOK,
                tags=["phishing", "incident_response"],
                uow=uow
            )
            synced.append(rec1)

            rec2 = await cls.create_or_sync_knowledge(
                title="ransomware forensics investigation",
                content="Ransomware decryption recovery steps.",
                knowledge_type=KnowledgeType.FORENSICS,
                tags=["ransomware", "forensics"],
                uow=uow
            )
            synced.append(rec2)
            await uow.commit()

        for r in synced:
            cls._knowledge[r.id] = r
            cls._fingerprint_lookup[r.knowledge_fingerprint] = r.id

        return synced

    @classmethod
    async def transition_status(
        cls, knowledge_id: uuid.UUID, new_status: KnowledgeStatus
    ) -> SecurityKnowledgeRecord:
        """Safely transition GRC knowledge status enforcing forward-only rules and terminal states."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            record = await uow.knowledge_repo.get_by_id(knowledge_id)
            if not record:
                raise ValueError(f"Knowledge record {knowledge_id} not found")

            current_status_enum = KnowledgeStatus(record.status)
            if current_status_enum == KnowledgeStatus.ARCHIVED:
                return record

            allowed = cls.ALLOWED_TRANSITIONS.get(current_status_enum, set())
            if new_status not in allowed:
                raise ValueError(f"Invalid transition from {record.status} to {new_status.value}")

            old_status = record.status
            record.status = new_status.value
            record.updated_at = datetime.now(timezone.utc)
            record.version += 1

            if new_status == KnowledgeStatus.APPROVED:
                record.confidence_score = KnowledgeRelevanceService.calculate_confidence(True)

            event_map = {
                KnowledgeStatus.REVIEW: "REVIEW",
                KnowledgeStatus.APPROVED: "APPROVED",
                KnowledgeStatus.ARCHIVED: "ARCHIVED",
            }
            event_type = event_map.get(new_status, "STATUS_CHANGED")

            hist = SecurityKnowledgeHistory(
                knowledge_id=record.id,
                event_type=event_type,
                details=f"Status transitioned from {old_status} to {new_status.value}",
                tenant_id=tenant_id
            )
            uow.session.add(hist)

            event = IntelligenceEvent(
                tenant_id=tenant_id,
                domain="knowledge",
                entity_id=record.id,
                event_type="knowledge.updated" if new_status != KnowledgeStatus.ARCHIVED else "knowledge.archived",
                payload={"id": str(record.id), "status": record.status},
                status="pending"
            )
            uow.session.add(event)

            audit = AuditLog(
                tenant_id=tenant_id,
                actor_id=record.created_by,
                action="transition_knowledge",
                target_type="knowledge",
                target_id=record.id,
                metadata_json={"old_status": old_status, "new_status": record.status},
                timestamp=datetime.now(timezone.utc)
            )
            uow.session.add(audit)

            await uow.commit()

            cls._knowledge[record.id] = record
            cls._fingerprint_lookup[record.knowledge_fingerprint] = record.id
            return record

    @classmethod
    async def recalculate_knowledge(cls) -> None:
        """Recalculate GRC knowledge scores and statuses deterministically (derived intelligence)."""
        from src.services.knowledge_severity_registry import KnowledgeSeverityRegistry
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        
        async with UnitOfWork() as uow:
            records = await uow.knowledge_repo.list()
            active_records = [r for r in records if not r.is_deleted]
            for record in active_records:
                if record.status == KnowledgeStatus.ARCHIVED.value:
                    continue

                old_relevance = float(record.relevance_score)
                old_confidence = float(record.confidence_score)
                old_severity = KnowledgeSeverityRegistry.determine_severity(old_relevance)

                # Recalculate
                new_relevance = KnowledgeRelevanceService.calculate_relevance(record.title, record.content_markdown)
                new_confidence = KnowledgeRelevanceService.calculate_confidence(record.status == KnowledgeStatus.APPROVED.value)
                new_severity = KnowledgeSeverityRegistry.determine_severity(new_relevance)

                changed = False
                if float(record.relevance_score) != new_relevance:
                    record.relevance_score = new_relevance
                    changed = True
                    hist = SecurityKnowledgeHistory(
                        knowledge_id=record.id,
                        event_type="RELEVANCE_CHANGED",
                        details=f"Relevance score updated from {old_relevance} to {new_relevance}",
                        tenant_id=tenant_id
                    )
                    uow.session.add(hist)

                if float(record.confidence_score) != new_confidence:
                    record.confidence_score = new_confidence
                    changed = True
                    hist = SecurityKnowledgeHistory(
                        knowledge_id=record.id,
                        event_type="CONFIDENCE_CHANGED",
                        details=f"Confidence score updated from {old_confidence} to {new_confidence}",
                        tenant_id=tenant_id
                    )
                    uow.session.add(hist)

                if old_severity != new_severity:
                    changed = True
                    hist = SecurityKnowledgeHistory(
                        knowledge_id=record.id,
                        event_type="SEVERITY_CHANGED",
                        details=f"Severity level updated from {old_severity} to {new_severity}",
                        tenant_id=tenant_id
                    )
                    uow.session.add(hist)

                if changed:
                    record.updated_at = datetime.now(timezone.utc)
                    record.version += 1
                    
                    event = IntelligenceEvent(
                        tenant_id=tenant_id,
                        domain="knowledge",
                        entity_id=record.id,
                        event_type="knowledge.updated",
                        payload={"id": str(record.id), "relevance_score": float(record.relevance_score)},
                        status="pending"
                    )
                    uow.session.add(event)

            await uow.commit()

            # Refresh cache
            for r in active_records:
                cls._knowledge[r.id] = r
                cls._fingerprint_lookup[r.knowledge_fingerprint] = r.id

    @classmethod
    def to_response(cls, record: SecurityKnowledgeRecord) -> KnowledgeRecordResponse:
        return KnowledgeRecordResponse(
            knowledge_id=record.id,
            knowledge_fingerprint=record.knowledge_fingerprint,
            knowledge_type=KnowledgeType(record.knowledge_type),
            title=record.title,
            content=record.content_markdown,
            relevance_score=float(record.relevance_score),
            confidence_score=float(record.confidence_score),
            status=KnowledgeStatus(record.status),
            tags=record.tags,
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
