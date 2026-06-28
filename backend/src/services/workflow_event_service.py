import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class WorkflowEventService:
    # In-memory tracking of emitted events for testing and lightweight queries
    _events: List[dict] = []

    @classmethod
    def clear_events(cls) -> None:
        """Clear all tracked workflow events."""
        cls._events.clear()

    @classmethod
    def get_events(cls) -> List[dict]:
        """Get all tracked workflow events."""
        return list(cls._events)

    @classmethod
    async def emit_event(
        cls,
        db: AsyncSession,
        event_type: str,
        correlation_id: Optional[uuid.UUID] = None,
        payload: Optional[dict] = None,
    ) -> Optional[WorkflowEvent]:
        """Query the latest workflow and emit a workflow event attached to it."""
        from src.infrastructure.database.models import Workflow, WorkflowEvent
        
        q_wf = select(Workflow).order_by(Workflow.created_at.desc()).limit(1)
        res_wf = await db.execute(q_wf)
        wf = res_wf.scalar_one_or_none()
        
        event_id = uuid.uuid4()
        evt_dict = {
            "event_id": str(event_id),
            "event_type": event_type,
            "correlation_id": str(correlation_id) if correlation_id else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(payload or {}),
        }
        cls._events.append(evt_dict)

        if wf:
            event = WorkflowEvent(
                id=event_id,
                workflow_id=wf.id,
                event_type=event_type,
                correlation_id=correlation_id,
                payload=evt_dict,
                timestamp=datetime.now(timezone.utc),
            )
            db.add(event)
            await db.commit()
            return event
        return None
