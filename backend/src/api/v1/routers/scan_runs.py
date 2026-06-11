import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.user import StandardResponse
from src.domain.entities.workflow import ScanRunResponse
from src.infrastructure.database.models import User
from src.infrastructure.database.session import get_db
from src.services.scope_service import get_scope_by_id
from src.services.workflow_service import (
    cancel_scan_run,
    get_scan_run_by_id,
    get_workflow_by_id,
)

router = APIRouter(prefix="/scan_runs", tags=["scan_runs"])


async def check_scan_run_ownership(
    db: AsyncSession, scan_run, current_user: User
):
    """Verify that a non-admin user owns either the parent workflow or scope."""
    if current_user.role == "admin":
        return

    # Check workflow ownership
    if scan_run.workflow_id:
        workflow = await get_workflow_by_id(db, scan_run.workflow_id)
        if workflow and workflow.owner_id == current_user.id:
            return

    # Fallback to scope ownership
    if scan_run.scope_id:
        scope = await get_scope_by_id(db, scan_run.scope_id)
        if scope and scope.owner_id == current_user.id:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: You do not own this scan run resource",
    )


@router.get("/{id}", response_model=StandardResponse[ScanRunResponse])
async def get_scan_run_details(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[ScanRunResponse]:
    """Retrieve details for a specific ScanRun. Ownership checks applied."""
    scan_run = await get_scan_run_by_id(db, id)
    if not scan_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ScanRun not found"
        )
    await check_scan_run_ownership(db, scan_run, current_user)
    return StandardResponse(data=ScanRunResponse.model_validate(scan_run))


@router.post("/{id}/cancel", response_model=StandardResponse[bool])
async def request_run_cancellation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[bool]:
    """Cancel a pending or running ScanRun execution."""
    scan_run = await get_scan_run_by_id(db, id)
    if not scan_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ScanRun not found"
        )
    await check_scan_run_ownership(db, scan_run, current_user)

    success = await cancel_scan_run(db, id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel scan run. It might not be in a cancellable state.",
        )
    return StandardResponse(data=True)
