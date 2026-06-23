import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.user import StandardResponse
from src.domain.entities.workflow import (
    WorkflowCreate,
    WorkflowEventResponse,
    WorkflowResponse,
    WorkflowStartRequest,
    WorkflowStartResponse,
    WorkflowUpdate,
)
from src.infrastructure.database.models import User
from src.infrastructure.database.session import get_db
from src.services.scope_service import get_scope_by_id
from src.services.workflow_service import (
    create_workflow,
    delete_workflow,
    get_workflow_by_id,
    get_workflow_events,
    list_workflows,
    start_workflow,
    update_workflow,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


def check_workflow_ownership(workflow, current_user: User):
    """Enforce ownership validation: non-admin users must own the workflow."""
    if current_user.role != "admin" and (
        workflow.owner_id is None or workflow.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permissions to access this workflow",
        )


@router.get("", response_model=StandardResponse[List[WorkflowResponse]])
async def list_user_workflows(
    page: int = 1,
    page_size: int = 50,
    owner_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[WorkflowResponse]]:
    """List workflows with pagination. Admin gets all; Operator/Reader gets owned."""
    if current_user.role == "admin":
        if owner_id:
            workflows, total = await list_workflows(db, owner_id, page, page_size)
        else:
            workflows, total = await list_workflows(db, None, page, page_size)
    else:
        workflows, total = await list_workflows(db, current_user.id, page, page_size)

    return StandardResponse(
        data=[WorkflowResponse.model_validate(w) for w in workflows],
        meta={"total": total, "page": page, "page_size": page_size},
    )


@router.post(
    "",
    response_model=StandardResponse[WorkflowResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_new_workflow(
    workflow_in: WorkflowCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[WorkflowResponse]:
    """Create a new workflow definition. Admin and Operator roles only."""
    try:
        new_wf = await create_workflow(db, workflow_in, owner_id=current_user.id)
        response.headers["Location"] = f"/api/v1/workflows/{new_wf.id}"
        return StandardResponse(data=WorkflowResponse.model_validate(new_wf))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{id}", response_model=StandardResponse[WorkflowResponse])
async def get_workflow_details(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[WorkflowResponse]:
    """Retrieve details for a specific workflow. Ownership checks applied."""
    workflow = await get_workflow_by_id(db, id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )
    check_workflow_ownership(workflow, current_user)
    return StandardResponse(data=WorkflowResponse.model_validate(workflow))


@router.put("/{id}", response_model=StandardResponse[WorkflowResponse])
async def update_existing_workflow(
    id: uuid.UUID,
    workflow_in: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[WorkflowResponse]:
    """Update an existing workflow. Admin/Operator owner only."""
    workflow = await get_workflow_by_id(db, id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )
    check_workflow_ownership(workflow, current_user)
    try:
        updated = await update_workflow(db, id, workflow_in)
        return StandardResponse(data=WorkflowResponse.model_validate(updated))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{id}", response_model=StandardResponse[bool])
async def delete_existing_workflow(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[bool]:
    """Delete a workflow. Admin/Operator owner only."""
    workflow = await get_workflow_by_id(db, id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )
    check_workflow_ownership(workflow, current_user)
    success = await delete_workflow(db, id)
    return StandardResponse(data=success)


@router.post(
    "/{id}/start",
    response_model=StandardResponse[WorkflowStartResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_workflow_execution(
    id: uuid.UUID,
    payload: WorkflowStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[WorkflowStartResponse]:
    """Start workflow execution. Validates scope ownership and workflow ownership."""
    workflow = await get_workflow_by_id(db, id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )
    check_workflow_ownership(workflow, current_user)

    # Validate that user owns the target scope
    scope = await get_scope_by_id(db, payload.scope_id)
    if not scope:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scope not found"
        )
    if current_user.role != "admin" and (
        scope.owner_id is None or scope.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not own the scope required for this workflow",
        )

    scan_run = await start_workflow(db, id, payload.scope_id, actor_id=current_user.id)
    return StandardResponse(
        data=WorkflowStartResponse(
            workflow_id=id, run_id=scan_run.id, status="accepted"
        )
    )


@router.get(
    "/{id}/events",
    response_model=StandardResponse[List[WorkflowEventResponse]],
)
async def get_lifecycle_events(
    id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[WorkflowEventResponse]]:
    """Retrieve paginated lifecycle events for a specific workflow."""
    workflow = await get_workflow_by_id(db, id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )
    check_workflow_ownership(workflow, current_user)

    events, total = await get_workflow_events(db, id, page, page_size)
    return StandardResponse(
        data=[WorkflowEventResponse.model_validate(e) for e in events],
        meta={"total": total, "page": page, "page_size": page_size},
    )
