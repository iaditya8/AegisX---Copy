import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.user import StandardResponse
from src.domain.entities.security_program import (
    ProgramSeverity,
    ProgramStatus,
    KPIStatus,
    KRIStatus,
    SecurityProgramResponse,
    ProgramObjectiveResponse,
    ProgramInitiativeResponse,
)
from src.infrastructure.database.models import Scope, User, Asset
from src.infrastructure.database.session import get_db
from src.services.security_program_service import SecurityProgramService, ProgramObjectiveRecord, ProgramInitiativeRecord
from src.services.program_history_service import ProgramHistoryService
from src.services.program_correlation_service import ProgramCorrelationService
from src.services.program_drift_service import ProgramDriftService
from src.services.security_program_snapshot_service import SecurityProgramSnapshotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/security-program", tags=["security-program"])


class ObjectiveRequest(BaseModel):
    name: str
    description: str
    completion_percentage: float = 0.0


class InitiativeRequest(BaseModel):
    name: str
    description: str
    status: str = "PLANNED"
    completion_percentage: float = 0.0


class CreateProgramRequest(BaseModel):
    name: str
    description: str
    category: str
    severity: ProgramSeverity
    objectives: List[ObjectiveRequest] = []
    initiatives: List[InitiativeRequest] = []
    scope_id: Optional[uuid.UUID] = None


class TransitionStatusRequest(BaseModel):
    status: ProgramStatus


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

@router.get("", response_model=StandardResponse[List[SecurityProgramResponse]])
async def list_programs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[SecurityProgramResponse]]:
    """List all programs, filtered by scope ownership."""
    programs = SecurityProgramService.get_all_programs()

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        programs = [p for p in programs if p.scope_id is None or p.scope_id in allowed_scopes]

    data = [SecurityProgramService.to_response(p) for p in programs]
    return StandardResponse(data=data)


@router.get("/active", response_model=StandardResponse[List[SecurityProgramResponse]])
async def list_active_programs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[SecurityProgramResponse]]:
    """List all active/under_review programs, filtered by scope ownership."""
    programs = SecurityProgramService.get_all_programs()
    programs = [p for p in programs if p.status in [ProgramStatus.ACTIVE, ProgramStatus.UNDER_REVIEW]]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        programs = [p for p in programs if p.scope_id is None or p.scope_id in allowed_scopes]

    data = [SecurityProgramService.to_response(p) for p in programs]
    return StandardResponse(data=data)


@router.get("/drift", response_model=StandardResponse[List[Dict]])
async def list_program_drift(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[Dict]]:
    """List all program drift events."""
    return StandardResponse(data=[])


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
    snap = await SecurityProgramSnapshotService.generate_snapshot(db, scope_id)
    return StandardResponse(data=snap)


@router.get("/{id}", response_model=StandardResponse[SecurityProgramResponse])
async def get_program_details(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[SecurityProgramResponse]:
    """Retrieve details of a specific program."""
    program = SecurityProgramService.get_program(id)
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found",
        )
    if program.scope_id:
        await check_scope_ownership(db, program.scope_id, current_user)

    data = SecurityProgramService.to_response(program)
    return StandardResponse(data=data)


@router.post("", response_model=StandardResponse[SecurityProgramResponse], status_code=status.HTTP_201_CREATED)
async def create_program(
    req: CreateProgramRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[SecurityProgramResponse]:
    """Manually create or synchronize a security program."""
    if req.scope_id:
        await check_scope_ownership(db, req.scope_id, current_user)

    objectives = [
        ProgramObjectiveRecord(uuid.uuid4(), o.name, o.description, o.completion_percentage)
        for o in req.objectives
    ]
    initiatives = [
        ProgramInitiativeRecord(uuid.uuid4(), i.name, i.description, i.status, i.completion_percentage)
        for i in req.initiatives
    ]

    record = await SecurityProgramService.create_or_sync_program(
        name=req.name,
        description=req.description,
        category=req.category,
        severity=req.severity,
        objectives=objectives,
        initiatives=initiatives,
        scope_id=req.scope_id,
    )
    data = SecurityProgramService.to_response(record)
    return StandardResponse(data=data)


@router.post("/{id}/transition", response_model=StandardResponse[SecurityProgramResponse])
async def transition_program_status(
    id: uuid.UUID,
    req: TransitionStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[SecurityProgramResponse]:
    """Transition program status safely."""
    program = SecurityProgramService.get_program(id)
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found",
        )
    if program.scope_id:
        await check_scope_ownership(db, program.scope_id, current_user)

    if program.status in [ProgramStatus.COMPLETED, ProgramStatus.CLOSED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify status of a completed or closed program",
        )

    record = await SecurityProgramService.transition_program_status(id, req.status)
    data = SecurityProgramService.to_response(record)
    return StandardResponse(data=data)
