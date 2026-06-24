import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.remediation import RemediationResponse, RemediationStatus
from src.domain.entities.user import StandardResponse
from src.infrastructure.database.models import Asset, User
from src.infrastructure.database.session import get_db
from src.services.remediation_service import RemediationRecord, RemediationService
from src.services.scope_service import get_scope_by_id

router = APIRouter(tags=["remediations"])


# --- Request Bodies ---


class AssignOwnerRequest(BaseModel):
    owner: str


class ExceptionRequest(BaseModel):
    reason: str
    approved_by: str


# --- Helper Checks ---


async def check_asset_ownership(
    db: AsyncSession, asset: Asset, current_user: User
) -> None:
    """Enforce scope ownership check for non-admin operators."""
    if current_user.role == "admin":
        return
    if not asset.scope_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permissions to access this asset",
        )
    scope = await get_scope_by_id(db, asset.scope_id)
    if not scope or scope.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permissions to access this asset",
        )


async def check_remediation_ownership(
    db: AsyncSession, record: RemediationRecord, current_user: User
) -> None:
    """Verify current user has access to the parent asset of this remediation."""
    asset = await db.get(Asset, record.asset_id)
    if not asset or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent asset not found",
        )
    await check_asset_ownership(db, asset, current_user)


def to_response(r: RemediationRecord) -> RemediationResponse:
    """Map in-memory RemediationRecord to Pydantic RemediationResponse."""
    return RemediationResponse(
        remediation_id=r.remediation_id,
        recommendation_fingerprint=r.recommendation_fingerprint,
        status=r.status,
        owner=r.owner,
        due_date=r.due_date,
        created_at=r.created_at,
        updated_at=r.updated_at,
        reason=r.reason,
        approved_by=r.approved_by,
        exception_approved_at=r.exception_approved_at,
    )


# --- API Routes ---


@router.get(
    "/remediations/assets/{id}",
    response_model=StandardResponse[List[RemediationResponse]],
)
async def list_asset_remediations(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[List[RemediationResponse]]:
    """Retrieve all remediation workflows for a specific asset."""
    asset = await db.get(Asset, id)
    if not asset or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )
    await check_asset_ownership(db, asset, current_user)
    records = RemediationService.get_remediations_by_asset(id)
    return StandardResponse(data=[to_response(r) for r in records])


@router.get(
    "/remediations/{id}",
    response_model=StandardResponse[RemediationResponse],
)
async def get_remediation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[RemediationResponse]:
    """Retrieve details of a specific remediation workflow."""
    record = RemediationService.get_remediation(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remediation not found",
        )
    await check_remediation_ownership(db, record, current_user)
    return StandardResponse(data=to_response(record))


@router.post(
    "/remediations/{id}/assign",
    response_model=StandardResponse[RemediationResponse],
)
async def assign_remediation_owner(
    id: uuid.UUID,
    body: AssignOwnerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[RemediationResponse]:
    """Assign an owner to a remediation workflow."""
    record = RemediationService.get_remediation(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remediation not found",
        )
    await check_remediation_ownership(db, record, current_user)
    updated = await RemediationService.assign_owner(
        db, id, body.owner, actor_id=current_user.id
    )
    return StandardResponse(data=to_response(updated))


@router.post(
    "/remediations/{id}/start",
    response_model=StandardResponse[RemediationResponse],
)
async def start_remediation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[RemediationResponse]:
    """Set remediation status to IN_PROGRESS."""
    record = RemediationService.get_remediation(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remediation not found",
        )
    await check_remediation_ownership(db, record, current_user)
    try:
        updated = await RemediationService.update_status(
            db, id, RemediationStatus.IN_PROGRESS, actor_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return StandardResponse(data=to_response(updated))


@router.post(
    "/remediations/{id}/complete",
    response_model=StandardResponse[RemediationResponse],
)
async def complete_remediation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[RemediationResponse]:
    """Set remediation status to REMEDIATED."""
    record = RemediationService.get_remediation(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remediation not found",
        )
    await check_remediation_ownership(db, record, current_user)
    try:
        updated = await RemediationService.update_status(
            db, id, RemediationStatus.REMEDIATED, actor_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return StandardResponse(data=to_response(updated))


@router.post(
    "/remediations/{id}/accept-risk",
    response_model=StandardResponse[RemediationResponse],
)
async def accept_remediation_risk(
    id: uuid.UUID,
    body: ExceptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[RemediationResponse]:
    """Exempt remediation workflow by marking status as ACCEPTED_RISK."""
    record = RemediationService.get_remediation(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remediation not found",
        )
    await check_remediation_ownership(db, record, current_user)
    try:
        updated = await RemediationService.update_status(
            db=db,
            remediation_id=id,
            status=RemediationStatus.ACCEPTED_RISK,
            actor_id=current_user.id,
            reason=body.reason,
            approved_by=body.approved_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return StandardResponse(data=to_response(updated))


@router.post(
    "/remediations/{id}/false-positive",
    response_model=StandardResponse[RemediationResponse],
)
async def mark_remediation_false_positive(
    id: uuid.UUID,
    body: ExceptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[RemediationResponse]:
    """Exempt remediation workflow by marking status as FALSE_POSITIVE."""
    record = RemediationService.get_remediation(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remediation not found",
        )
    await check_remediation_ownership(db, record, current_user)
    try:
        updated = await RemediationService.update_status(
            db=db,
            remediation_id=id,
            status=RemediationStatus.FALSE_POSITIVE,
            actor_id=current_user.id,
            reason=body.reason,
            approved_by=body.approved_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return StandardResponse(data=to_response(updated))


@router.post(
    "/remediations/{id}/defer",
    response_model=StandardResponse[RemediationResponse],
)
async def defer_remediation(
    id: uuid.UUID,
    body: ExceptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[RemediationResponse]:
    """Defer remediation workflow by marking status as DEFERRED."""
    record = RemediationService.get_remediation(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remediation not found",
        )
    await check_remediation_ownership(db, record, current_user)
    try:
        updated = await RemediationService.update_status(
            db=db,
            remediation_id=id,
            status=RemediationStatus.DEFERRED,
            actor_id=current_user.id,
            reason=body.reason,
            approved_by=body.approved_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return StandardResponse(data=to_response(updated))
