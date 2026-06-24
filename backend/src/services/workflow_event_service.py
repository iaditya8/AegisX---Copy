import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Workflow, WorkflowEvent


class WorkflowEventService:
    @classmethod
    async def emit_event(
        cls,
        db: AsyncSession,
        event_type: str,
        correlation_id: Optional[uuid.UUID] = None,
        payload: Optional[dict] = None,
    ) -> Optional[WorkflowEvent]:
        """Query the latest workflow and emit a workflow event attached to it."""
        q_wf = select(Workflow).order_by(Workflow.created_at.desc()).limit(1)
        res_wf = await db.execute(q_wf)
        wf = res_wf.scalar_one_or_none()
        if wf:
            event_id = uuid.uuid4()
            event = WorkflowEvent(
                id=event_id,
                workflow_id=wf.id,
                event_type=event_type,
                correlation_id=correlation_id,
                payload={
                    "event_id": str(event_id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **(payload or {}),
                },
                timestamp=datetime.now(timezone.utc),
            )
            db.add(event)
            await db.commit()
            return event
        return None
