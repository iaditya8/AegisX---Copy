import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.user import StandardResponse
from src.domain.entities.control_validation import (
    ControlSeverity,
    ControlStatus,
    ValidationStatus,
    ControlType,
    ControlResponse,
    ValidationResponse,
)
from src.infrastructure.database.models import Scope, User, Asset
from src.infrastructure.database.session import get_db
from src.services.control_validation_service import ControlValidationService
from src.services.control_history_service import ControlHistoryService
from src.services.control_correlation_service import ControlCorrelationService
from src.services.control_drift_service import ControlDriftService
from src.services.control_validation_snapshot_service import ControlValidationSnapshotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/control-validation", tags=["control-validation"])


class CreateControlRequest(BaseModel):
    name: str
    description: str
    control_type: ControlType
    severity: ControlSeverity
    attack_techniques: List[str]
    scope_id: Optional[uuid.UUID] = None


class ValidateControlRequest(BaseModel):
    attack_technique: str
    validation_status: ValidationStatus
    evidence: str


# --- Helper Checks ---

async def check_scope_ownership(
    db: AsyncSession, scope_id: uuid.UUID, current_user: User
) -> None:
    """Enforce scope ownership check for non-admin users."""
    if current_user.role == "admin":
        return

    scope = await get_scope_by_id(db, scope_id)
    if not scope or scope.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scope not found",
        )

    if scope.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not own this scope",
        )


async def get_allowed_scope_ids(db: AsyncSession, current_user: User) -> set:
    """Retrieve all scope IDs owned by the current user."""
    if current_user.role == "admin":
        return set()

    q_scopes = select(Scope).where(
        Scope.owner_id == current_user.id, Scope.deleted_at.is_(None)
    )
    res_scopes = await db.execute(q_scopes)
    scopes = res_scopes.scalars().all()
    return {s.id for s in scopes}


# --- Endpoints ---

@router.get("", response_model=StandardResponse[List[ControlResponse]])
async def list_controls(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[ControlResponse]]:
    """List all controls, filtered by scope ownership."""
    controls = ControlValidationService.get_all_controls()

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        controls = [c for c in controls if c.scope_id is None or c.scope_id in allowed_scopes]

    data = [ControlValidationService.to_response(c) for c in controls]
    return StandardResponse(data=data)


@router.get("/active", response_model=StandardResponse[List[ControlResponse]])
async def list_active_controls(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[ControlResponse]]:
    """List all active controls, filtered by scope ownership."""
    controls = ControlValidationService.get_all_controls()
    controls = [c for c in controls if c.status == ControlStatus.ACTIVE]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        controls = [c for c in controls if c.scope_id is None or c.scope_id in allowed_scopes]

    data = [ControlValidationService.to_response(c) for c in controls]
    return StandardResponse(data=data)


@router.get("/degraded", response_model=StandardResponse[List[ControlResponse]])
async def list_degraded_controls(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[ControlResponse]]:
    """List all degraded controls, filtered by scope ownership."""
    controls = ControlValidationService.get_all_controls()
    controls = [c for c in controls if c.status == ControlStatus.DEGRADED]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        controls = [c for c in controls if c.scope_id is None or c.scope_id in allowed_scopes]

    data = [ControlValidationService.to_response(c) for c in controls]
    return StandardResponse(data=data)


@router.get("/failed", response_model=StandardResponse[List[ControlResponse]])
async def list_failed_controls(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[ControlResponse]]:
    """List all failed controls, filtered by scope ownership."""
    controls = ControlValidationService.get_all_controls()
    controls = [c for c in controls if c.status == ControlStatus.FAILED]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        controls = [c for c in controls if c.scope_id is None or c.scope_id in allowed_scopes]

    data = [ControlValidationService.to_response(c) for c in controls]
    return StandardResponse(data=data)


@router.get("/drift", response_model=StandardResponse[List[Dict]])
async def list_control_drift(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[Dict]]:
    """List all control drift events (workflow events)."""
    # Simply return mocked or recorded drift payload lists for this sprint
    return StandardResponse(data=[])


@router.get("/coverage", response_model=StandardResponse[Dict[str, float]])
async def list_control_coverage(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict[str, float]]:
    """Retrieve control coverage statistics across scope."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    else:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Non-admin users must specify scope_id",
            )
    cov = await ControlCoverageService.calculate_coverage(db, scope_id)
    return StandardResponse(data=cov)


@router.get("/summary", response_model=StandardResponse[Dict])
async def get_summary_snapshot(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict]:
    """Rebuild and return the summary snapshot."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    else:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Non-admin users must specify scope_id",
            )
    snap = await ControlValidationSnapshotService.generate_snapshot(db, scope_id)
    return StandardResponse(data=snap)


@router.get("/{id}", response_model=StandardResponse[ControlResponse])
async def get_control_details(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[ControlResponse]:
    """Retrieve details of a specific control."""
    control = ControlValidationService.get_control(id)
    if not control:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Control not found",
        )
    if control.scope_id:
        await check_scope_ownership(db, control.scope_id, current_user)

    data = ControlValidationService.to_response(control)
    return StandardResponse(data=data)


@router.post("", response_model=StandardResponse[ControlResponse], status_code=status.HTTP_201_CREATED)
async def create_control(
    req: CreateControlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ControlResponse]:
    """Manually create or synchronize a security control."""
    if req.scope_id:
        await check_scope_ownership(db, req.scope_id, current_user)

    record = await ControlValidationService.create_or_sync_control(
        name=req.name,
        description=req.description,
        control_type=req.control_type,
        severity=req.severity,
        attack_techniques=req.attack_techniques,
        scope_id=req.scope_id,
    )
    data = ControlValidationService.to_response(record)
    return StandardResponse(data=data)


@router.post("/{id}/validate", response_model=StandardResponse[ValidationResponse])
async def validate_control(
    id: uuid.UUID,
    req: ValidateControlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ValidationResponse]:
    """Execute a manual control validation run."""
    control = ControlValidationService.get_control(id)
    if not control:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Control not found",
        )
    if control.scope_id:
        await check_scope_ownership(db, control.scope_id, current_user)

    if control.status == ControlStatus.RETIRED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot validate a retired control",
        )

    if req.attack_technique not in control.attack_techniques:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attack technique not mapped to this control",
        )

    val = await ControlValidationService.execute_validation(
        db=db,
        control_id=id,
        attack_technique=req.attack_technique,
        status=req.validation_status,
        evidence=req.evidence,
    )
    return StandardResponse(data=val)


@router.post("/{id}/retire", response_model=StandardResponse[ControlResponse])
async def retire_control(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ControlResponse]:
    """Transition control status to RETIRED (terminal state)."""
    control = ControlValidationService.get_control(id)
    if not control:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Control not found",
        )
    if control.scope_id:
        await check_scope_ownership(db, control.scope_id, current_user)

    record = ControlValidationService.retire_control(id)
    data = ControlValidationService.to_response(record)
    return StandardResponse(data=data)
