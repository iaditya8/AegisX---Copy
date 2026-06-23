import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.workflow import WorkflowCreate, WorkflowUpdate
from src.infrastructure.celery.worker import execute_workflow_task
from src.infrastructure.database.models import ScanRun, Workflow, WorkflowEvent


async def get_workflow_by_id(
    db: AsyncSession, workflow_id: uuid.UUID
) -> Optional[Workflow]:
    """Retrieve a workflow by ID."""
    return await db.get(Workflow, workflow_id)


async def list_workflows(
    db: AsyncSession,
    owner_id: Optional[uuid.UUID] = None,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[Workflow], int]:
    """List workflows with pagination, optionally filtered by owner."""
    offset = (page - 1) * page_size
    query = select(Workflow).order_by(Workflow.created_at.desc())
    count_query = select(func.count(Workflow.id))

    if owner_id:
        query = query.where(Workflow.owner_id == owner_id)
        count_query = count_query.where(Workflow.owner_id == owner_id)

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    result = await db.execute(query.offset(offset).limit(page_size))
    workflows = list(result.scalars().all())
    return workflows, total


async def check_deprecated_plugins(db: AsyncSession, definition: dict) -> None:
    if not isinstance(definition, dict):
        return
    steps = definition.get("steps", [])
    if not isinstance(steps, list):
        return
    for step in steps:
        if not isinstance(step, dict):
            continue
        config = step.get("config", {})
        if not isinstance(config, dict):
            continue
        tools = config.get("tools", [])
        if isinstance(tools, str):
            tools = [tools]
        if not isinstance(tools, list):
            continue
        for tool in tools:
            if not isinstance(tool, str):
                continue
            from src.services.plugin_service import get_plugin_by_name

            plugin = await get_plugin_by_name(db, tool)
            if plugin and plugin.state == "deprecated":
                raise ValueError(
                    f"Cannot attach deprecated plugin '{tool}' to workflow"
                )


async def create_workflow(
    db: AsyncSession, workflow_in: WorkflowCreate, owner_id: uuid.UUID
) -> Workflow:
    """Create a new workflow definition with 'draft' state."""
    await check_deprecated_plugins(db, workflow_in.definition)
    db_wf = Workflow(
        owner_id=owner_id,
        name=workflow_in.name,
        definition=workflow_in.definition,
        state="draft",  # 'draft', 'active', 'disabled'
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(db_wf)
    await db.commit()
    await db.refresh(db_wf)
    return db_wf


async def update_workflow(
    db: AsyncSession, workflow_id: uuid.UUID, workflow_in: WorkflowUpdate
) -> Optional[Workflow]:
    """Update an existing workflow definition."""
    db_wf = await get_workflow_by_id(db, workflow_id)
    if not db_wf:
        return None

    if workflow_in.definition is not None:
        await check_deprecated_plugins(db, workflow_in.definition)

    update_data = workflow_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_wf, field, value)

    db_wf.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(db_wf)
    return db_wf


async def delete_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> bool:
    """Delete a workflow definition."""
    db_wf = await get_workflow_by_id(db, workflow_id)
    if not db_wf:
        return False

    await db.delete(db_wf)
    await db.commit()
    return True


async def start_workflow(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    scope_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> Optional[ScanRun]:
    """Initialize a ScanRun, set state to 'pending', and trigger background task."""
    workflow = await get_workflow_by_id(db, workflow_id)
    if not workflow:
        return None

    # Retrieve first step type from definition steps to assign ScanRun.type
    steps = workflow.definition.get("steps", [])
    first_step_type = steps[0].get("type", "discovery") if steps else "discovery"

    scan_run = ScanRun(
        workflow_id=workflow_id,
        scope_id=scope_id,
        type=first_step_type,
        status="pending",  # 'pending', 'running', 'completed', 'failed', 'cancelled'
        created_at=datetime.now(timezone.utc),
    )
    db.add(scan_run)
    await db.commit()
    await db.refresh(scan_run)

    # Trigger Celery background task
    execute_workflow_task.delay(str(workflow_id), str(scan_run.id), str(scope_id))

    return scan_run


async def get_scan_run_by_id(
    db: AsyncSession, scan_run_id: uuid.UUID
) -> Optional[ScanRun]:
    """Retrieve a ScanRun by ID."""
    return await db.get(ScanRun, scan_run_id)


async def cancel_scan_run(db: AsyncSession, scan_run_id: uuid.UUID) -> bool:
    """Request run cancellation by setting state to 'cancelled' in the DB."""
    scan_run = await get_scan_run_by_id(db, scan_run_id)
    if not scan_run:
        return False

    # Only cancel running or pending runs
    if scan_run.status not in ("pending", "running"):
        return False

    scan_run.status = "cancelled"
    scan_run.end_ts = datetime.now(timezone.utc)
    await db.commit()
    return True


async def get_workflow_events(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[WorkflowEvent], int]:
    """Retrieve lifecycle events for a specific workflow with pagination."""
    offset = (page - 1) * page_size
    query = (
        select(WorkflowEvent)
        .where(WorkflowEvent.workflow_id == workflow_id)
        .order_by(WorkflowEvent.timestamp.desc())
    )
    count_query = select(func.count(WorkflowEvent.id)).where(
        WorkflowEvent.workflow_id == workflow_id
    )

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    result = await db.execute(query.offset(offset).limit(page_size))
    events = list(result.scalars().all())
    return events, total


async def create_workflow_event(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    event_type: str,
    correlation_id: Optional[uuid.UUID] = None,
    payload: Optional[dict] = None,
) -> WorkflowEvent:
    """Persist a new workflow event."""
    db_evt = WorkflowEvent(
        workflow_id=workflow_id,
        event_type=event_type,
        correlation_id=correlation_id,
        payload=payload or {},
        timestamp=datetime.now(timezone.utc),
    )
    db.add(db_evt)
    await db.commit()
    await db.refresh(db_evt)
    return db_evt
