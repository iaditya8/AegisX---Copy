import uuid
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession


class KnowledgeSnapshotService:
    # Cache store: scope_id -> Snapshot dictionary
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear the knowledge snapshot cache."""
        cls._snapshots.clear()

    @classmethod
    def get_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Retrieve the cached GRC knowledge snapshot, defaulting to a minimal fallback if missing or corrupted."""
        snap = cls._snapshots.get(scope_id)
        if not snap or not isinstance(snap, dict) or "summary" not in snap:
            return {
                "summary": {
                    "total_knowledge_records": 0,
                    "active_knowledge_records": 0,
                    "archived_knowledge_records": 0,
                    "average_relevance_score": 0.0,
                    "average_confidence_score": 0.0,
                },
                "records": {},
            }
        return snap

    @classmethod
    async def generate_snapshot(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None
    ) -> dict:
        """Dynamically rebuild GRC knowledge snapshot stats from active records."""
        from src.services.security_knowledge_service import SecurityKnowledgeService
        from src.domain.entities.security_knowledge import KnowledgeStatus

        all_recs = SecurityKnowledgeService.get_all_knowledge()
        if scope_id:
            all_recs = [r for r in all_recs if r.scope_id == scope_id]

        total_recs = len(all_recs)
        active_count = sum(1 for r in all_recs if r.status in (KnowledgeStatus.ACTIVE, KnowledgeStatus.REVIEW, KnowledgeStatus.APPROVED))
        archived_count = sum(1 for r in all_recs if r.status == KnowledgeStatus.ARCHIVED)

        avg_relevance = (
            round(sum(r.relevance_score for r in all_recs) / total_recs, 2)
            if total_recs > 0
            else 0.0
        )
        avg_confidence = (
            round(sum(r.confidence_score for r in all_recs) / total_recs, 2)
            if total_recs > 0
            else 0.0
        )

        records_track = {}
        for r in all_recs:
            records_track[str(r.knowledge_id)] = {
                "knowledge_id": str(r.knowledge_id),
                "title": r.title,
                "knowledge_type": r.knowledge_type.value,
                "status": r.status.value,
                "relevance_score": r.relevance_score,
                "confidence_score": r.confidence_score,
            }

        snapshot = {
            "summary": {
                "total_knowledge_records": total_recs,
                "active_knowledge_records": active_count,
                "archived_knowledge_records": archived_count,
                "average_relevance_score": avg_relevance,
                "average_confidence_score": avg_confidence,
            },
            "records": records_track,
        }

        cls._snapshots[scope_id] = snapshot
        return snapshot
