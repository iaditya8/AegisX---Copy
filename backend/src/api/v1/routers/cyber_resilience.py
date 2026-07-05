import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.user import StandardResponse
from src.domain.entities.cyber_resilience import (
    ResilienceStatus,
    ServiceCriticality,
    CyberResilienceResponse,
    RecoveryObjectiveResponse,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.cyber_resilience_service import CyberResilienceService
from src.services.resilience_history_service import ResilienceHistoryService
from src.services.recovery_objective_service import RecoveryObjectiveService
from src.services.service_resilience_service import ServiceResilienceService
from src.services.cyber_resilience_snapshot_service import CyberResilienceSnapshotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/cyber-resilience", tags=["cyber-resilience"])


class CreateResilienceRequest(BaseModel):
    title: str
    description: str
    service_name: str
    service_criticality: ServiceCriticality
    scope_id: Optional[uuid.UUID] = None


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

@router.get("", response_model=StandardResponse[List[CyberResilienceResponse]])
async def list_resilience(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[CyberResilienceResponse]]:
    """List all cyber resilience records."""
    records = await CyberResilienceService.get_all_resilience()

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [CyberResilienceService.to_response(r) for r in records]
    return StandardResponse(data=data)


@router.get("/active", response_model=StandardResponse[List[CyberResilienceResponse]])
async def get_active(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[CyberResilienceResponse]]:
    """Get active cyber resilience records."""
    records = await CyberResilienceService.get_all_resilience()
    records = [r for r in records if r.status == ResilienceStatus.ACTIVE]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [CyberResilienceService.to_response(r) for r in records]
    return StandardResponse(data=data)


@router.get("/completed", response_model=StandardResponse[List[CyberResilienceResponse]])
async def get_completed(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[CyberResilienceResponse]]:
    """Get completed cyber resilience records."""
    records = await CyberResilienceService.get_all_resilience()
    records = [
        r
        for r in records
        if r.status in (ResilienceStatus.COMPLETED, ResilienceStatus.CLOSED)
    ]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [CyberResilienceService.to_response(r) for r in records]
    return StandardResponse(data=data)


@router.get("/critical-services", response_model=StandardResponse[List[CyberResilienceResponse]])
async def get_critical_services(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[CyberResilienceResponse]]:
    """Filter resilience records to critical services only."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)

    records = await ServiceResilienceService.get_critical_services(scope_id)

    if current_user.role != "admin" and not scope_id:
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [CyberResilienceService.to_response(r) for r in records]
    return StandardResponse(data=data)


@router.get("/objectives", response_model=StandardResponse[List[RecoveryObjectiveResponse]])
async def get_objectives(
    resilience_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[RecoveryObjectiveResponse]]:
    """Get objectives for a specific resilience record."""
    record = await CyberResilienceService.get_resilience(resilience_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resilience record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    data = RecoveryObjectiveService.get_objectives(resilience_id)
    return StandardResponse(data=data)


@router.get("/drift", response_model=StandardResponse[Dict])
async def get_drift(
    current_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[Dict]:
    """Retrieve resilience drift status logs."""
    return StandardResponse(data={"drift_logs": []})


@router.get("/summary", response_model=StandardResponse[Dict])
async def get_summary(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict]:
    """Get summary snapshot of cyber resilience status."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    else:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Non-admin users must specify scope_id",
            )
    snap = await CyberResilienceSnapshotService.generate_snapshot(db, scope_id)
    return StandardResponse(data=snap)


@router.post("", response_model=StandardResponse[CyberResilienceResponse], status_code=status.HTTP_201_CREATED)
async def create_resilience(
    req: CreateResilienceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[CyberResilienceResponse]:
    """Create a new cyber resilience record."""
    if req.scope_id:
        await check_scope_ownership(db, req.scope_id, current_user)

    record = await CyberResilienceService.create_or_sync_resilience(
        title=req.title,
        description=req.description,
        service_name=req.service_name,
        service_criticality=req.service_criticality,
        scope_id=req.scope_id,
    )
    data = CyberResilienceService.to_response(record)
    return StandardResponse(data=data)


@router.post("/{id}/activate", response_model=StandardResponse[CyberResilienceResponse])
async def activate_resilience(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[CyberResilienceResponse]:
    """Transition to ACTIVE."""
    record = await CyberResilienceService.get_resilience(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resilience record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status in (ResilienceStatus.COMPLETED, ResilienceStatus.CLOSED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of a completed or closed record",
        )

    res = await CyberResilienceService.transition_status(id, ResilienceStatus.ACTIVE)
    return StandardResponse(data=CyberResilienceService.to_response(res))


@router.post("/{id}/validate", response_model=StandardResponse[CyberResilienceResponse])
async def validate_resilience(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[CyberResilienceResponse]:
    """Transition to VALIDATED."""
    record = await CyberResilienceService.get_resilience(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resilience record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status in (ResilienceStatus.COMPLETED, ResilienceStatus.CLOSED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of a completed or closed record",
        )

    res = await CyberResilienceService.transition_status(id, ResilienceStatus.VALIDATED)
    return StandardResponse(data=CyberResilienceService.to_response(res))


@router.post("/{id}/complete", response_model=StandardResponse[CyberResilienceResponse])
async def complete_resilience(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[CyberResilienceResponse]:
    """Transition to COMPLETED."""
    record = await CyberResilienceService.get_resilience(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resilience record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status in (ResilienceStatus.COMPLETED, ResilienceStatus.CLOSED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of a completed or closed record",
        )

    res = await CyberResilienceService.transition_status(id, ResilienceStatus.COMPLETED)
    return StandardResponse(data=CyberResilienceService.to_response(res))


@router.post("/{id}/close", response_model=StandardResponse[CyberResilienceResponse])
async def close_resilience(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[CyberResilienceResponse]:
    """Transition to CLOSED."""
    record = await CyberResilienceService.get_resilience(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resilience record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status in (ResilienceStatus.COMPLETED, ResilienceStatus.CLOSED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of a completed or closed record",
        )

    res = await CyberResilienceService.transition_status(id, ResilienceStatus.CLOSED)
    return StandardResponse(data=CyberResilienceService.to_response(res))
