import asyncio
import threading
import uuid
from datetime import datetime, timezone

from celery import Celery
from src.core.config import settings
from src.infrastructure.database.models import ScanRun, Workflow, WorkflowEvent
from src.infrastructure.database.session import AsyncSessionLocal

celery_app = Celery("aegisx_worker", broker=settings.REDIS_URL)


def run_async_task(coro):
    """Run an async function synchronously in a safe separate thread.

    This avoids event loop conflicts.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop:
        result = []
        exception = []

        def target():
            try:
                res = asyncio.run(coro)
                result.append(res)
            except Exception as e:
                exception.append(e)

        t = threading.Thread(target=target)
        t.start()
        t.join()

        if exception:
            raise exception[0]
        return result[0] if result else None
    else:
        return asyncio.run(coro)


async def _execute_workflow_async(
    workflow_id: uuid.UUID, scan_run_id: uuid.UUID, scope_id: uuid.UUID
):
    async with AsyncSessionLocal() as db:
        workflow = await db.get(Workflow, workflow_id)
        scan_run = await db.get(ScanRun, scan_run_id)

        if not workflow or not scan_run:
            return

        # Check if already cancelled
        if scan_run.status == "cancelled":
            return

        # Transition ScanRun status to running
        scan_run.status = "running"
        scan_run.start_ts = datetime.now(timezone.utc)

        # Log workflow.started event
        start_event = WorkflowEvent(
            workflow_id=workflow_id,
            event_type="workflow.started",
            correlation_id=scan_run_id,
            payload={"scan_run_id": str(scan_run_id)},
            timestamp=datetime.now(timezone.utc),
        )
        db.add(start_event)
        await db.commit()

        steps = workflow.definition.get("steps", [])

        for index, step in enumerate(steps):
            # Check for cancellation before executing step
            await db.refresh(scan_run)
            if scan_run.status == "cancelled":
                cancel_event = WorkflowEvent(
                    workflow_id=workflow_id,
                    event_type="workflow.cancelled",
                    correlation_id=scan_run_id,
                    payload={
                        "scan_run_id": str(scan_run_id),
                        "last_completed_step_index": index - 1,
                    },
                    timestamp=datetime.now(timezone.utc),
                )
                db.add(cancel_event)
                await db.commit()
                return

            step_type = step.get("type", "unknown")

            # Log step.started event
            step_started_evt = WorkflowEvent(
                workflow_id=workflow_id,
                event_type="step.started",
                correlation_id=scan_run_id,
                payload={"step_index": index, "step_type": step_type},
                timestamp=datetime.now(timezone.utc),
            )
            db.add(step_started_evt)
            await db.commit()

            # Simulate step execution delay
            await asyncio.sleep(0.01)

            # Log step.completed event
            step_completed_evt = WorkflowEvent(
                workflow_id=workflow_id,
                event_type="step.completed",
                correlation_id=scan_run_id,
                payload={"step_index": index, "step_type": step_type},
                timestamp=datetime.now(timezone.utc),
            )
            db.add(step_completed_evt)
            await db.commit()

        # Update ScanRun to completed
        await db.refresh(scan_run)
        if scan_run.status != "cancelled":
            scan_run.status = "completed"
            scan_run.end_ts = datetime.now(timezone.utc)

            completed_evt = WorkflowEvent(
                workflow_id=workflow_id,
                event_type="workflow.completed",
                correlation_id=scan_run_id,
                payload={"scan_run_id": str(scan_run_id)},
                timestamp=datetime.now(timezone.utc),
            )
            db.add(completed_evt)
            await db.commit()


@celery_app.task(name="execute_workflow_task")
def execute_workflow_task(
    workflow_id_str: str, scan_run_id_str: str, scope_id_str: str
):
    workflow_id = uuid.UUID(workflow_id_str)
    scan_run_id = uuid.UUID(scan_run_id_str)
    scope_id = uuid.UUID(scope_id_str)
    return run_async_task(
        _execute_workflow_async(workflow_id, scan_run_id, scope_id)
    )
