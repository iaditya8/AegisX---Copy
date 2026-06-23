import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Workflow, WorkflowEvent
from src.services.audit_service import create_audit_entry


class RecommendationHistoryService:
    # in-memory store: fingerprint -> record dict
    # Record: {
    #   "recommendation_id": str,
    #   "created_at": datetime,
    #   "last_seen": datetime,
    #   "times_recomputed": int,
    #   "priority": str,
    #   "status": str
    # }
    _history: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_stale_recommendations(cls, days: int = 30) -> List[Dict[str, Any]]:
        """Return recommendations that haven't been seen or updated
        for a given number of days.
        """
        now = datetime.now(timezone.utc)
        stale = []
        for entry in cls._history.values():
            age_seconds = (now - entry["last_seen"]).total_seconds()
            if age_seconds > (days * 86400.0):
                stale.append(entry)
        return stale

    @classmethod
    def get_recommendation_age_days(cls, fingerprint: str) -> float:
        """Calculate the age of the recommendation in days."""
        entry = cls._history.get(fingerprint)
        if not entry:
            return 0.0
        now = datetime.now(timezone.utc)
        return (now - entry["created_at"]).total_seconds() / 86400.0

    @classmethod
    async def record_recommendation(
        cls,
        db: AsyncSession,
        fingerprint: str,
        asset_id: str,
        finding_id: Optional[str],
        priority: str,
        title: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Record recommendation creation or recomputation, handling priority
        updates and events.
        """
        now = datetime.now(timezone.utc)

        if fingerprint in cls._history:
            entry = cls._history[fingerprint]
            entry["times_recomputed"] += 1
            entry["last_seen"] = now

            old_priority = entry["priority"]
            if old_priority != priority:
                entry["priority"] = priority
                await cls._emit_priority_changed(
                    db, fingerprint, asset_id, old_priority, priority, actor_id
                )
        else:
            cls._history[fingerprint] = {
                "recommendation_id": fingerprint,
                "created_at": now,
                "last_seen": now,
                "times_recomputed": 0,
                "priority": priority,
                "status": "open",
            }
            await cls._emit_creation(
                db, fingerprint, asset_id, finding_id, priority, title, actor_id
            )

    @classmethod
    async def _emit_creation(
        cls,
        db: AsyncSession,
        fingerprint: str,
        asset_id: str,
        finding_id: Optional[str],
        priority: str,
        title: str,
        actor_id: Optional[uuid.UUID],
    ) -> None:
        # 1. Emit Audit Log
        try:
            target_uuid = uuid.UUID(asset_id)
        except ValueError:
            target_uuid = uuid.uuid4()

        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="recommendation.created",
            target_type="recommendation",
            target_id=target_uuid,
            metadata={
                "recommendation_id": fingerprint,
                "finding_id": finding_id,
                "priority": priority,
                "title": title,
            },
        )

        # 2. Emit Workflow Event
        q_wf = select(Workflow).order_by(Workflow.created_at.desc()).limit(1)
        res_wf = await db.execute(q_wf)
        wf = res_wf.scalar_one_or_none()
        if wf:
            event_id = uuid.uuid4()
            event = WorkflowEvent(
                id=event_id,
                workflow_id=wf.id,
                event_type="recommendation.created",
                correlation_id=None,
                payload={
                    "event_id": str(event_id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "recommendation_id": fingerprint,
                    "asset_id": asset_id,
                    "finding_id": finding_id,
                    "priority": priority,
                },
                timestamp=datetime.now(timezone.utc),
            )
            db.add(event)
            await db.commit()

    @classmethod
    async def _emit_priority_changed(
        cls,
        db: AsyncSession,
        fingerprint: str,
        asset_id: str,
        old_priority: str,
        new_priority: str,
        actor_id: Optional[uuid.UUID],
    ) -> None:
        try:
            target_uuid = uuid.UUID(asset_id)
        except ValueError:
            target_uuid = uuid.uuid4()

        # 1. Emit Audit Log
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="recommendation.priority_changed",
            target_type="recommendation",
            target_id=target_uuid,
            metadata={
                "recommendation_id": fingerprint,
                "old_priority": old_priority,
                "new_priority": new_priority,
            },
        )

        # 2. Emit Workflow Event
        q_wf = select(Workflow).order_by(Workflow.created_at.desc()).limit(1)
        res_wf = await db.execute(q_wf)
        wf = res_wf.scalar_one_or_none()
        if wf:
            event_id = uuid.uuid4()
            event = WorkflowEvent(
                id=event_id,
                workflow_id=wf.id,
                event_type="recommendation.priority_changed",
                correlation_id=None,
                payload={
                    "event_id": str(event_id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "recommendation_id": fingerprint,
                    "asset_id": asset_id,
                    "old_priority": old_priority,
                    "new_priority": new_priority,
                },
                timestamp=datetime.now(timezone.utc),
            )
            db.add(event)
            await db.commit()

    @classmethod
    def clear_history(cls) -> None:
        """Clear the in-memory history tracker."""
        cls._history.clear()
