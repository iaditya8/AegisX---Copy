import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.detection import (
    CoverageStatus,
    DetectionCoverageResponse,
    DetectionResponse,
    DetectionSeverity,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.detection_coverage_service import DetectionCoverageService
from src.services.detection_service import DetectionRecord, DetectionService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/detections", tags=["detections"])


class CreateDetectionRequest(BaseModel):
    name: str
    description: str
    severity: DetectionSeverity
    attack_techniques: List[str]
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


async def check_detection_ownership(
    db: AsyncSession, detection: DetectionRecord, current_user: User
) -> None:
    """Check if the user has access to a specific detection based on scope ownership."""
    if current_user.role == "admin":
        return

    if not detection.scope_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access organization-wide detections",
        )

    await check_scope_ownership(db, detection.scope_id, current_user)


async def get_allowed_scope_ids(db: AsyncSession, current_user: User) -> set:
    """Retrieve all scope IDs owned by the current non-admin user."""
    if current_user.role == "admin":
        return set()

    q_scopes = select(Scope).where(
        Scope.owner_id == current_user.id, Scope.deleted_at.is_(None)
    )
    res_scopes = await db.execute(q_scopes)
    scopes = res_scopes.scalars().all()
    return {s.id for s in scopes}


def to_detection_response(d: DetectionRecord) -> DetectionResponse:
    """Map a DetectionRecord to a DetectionResponse schema."""
    return DetectionResponse(
        detection_id=d.detection_id,
        detection_fingerprint=d.detection_fingerprint,
        name=d.name,
        description=d.description,
        severity=d.severity,
        status=d.status,
        attack_techniques=d.attack_techniques,
        created_at=d.created_at,
        updated_at=d.updated_at,
        scope_id=d.scope_id,
    )


# --- Endpoints ---


@router.get("", response_model=List[DetectionResponse])
async def list_detections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all detection rules, applying scope filtering for non-admins."""
    detections = DetectionService.get_all_detections()
    if current_user.role == "admin":
        return [to_detection_response(d) for d in detections]

    allowed_scopes = await get_allowed_scope_ids(db, current_user)
    filtered = [
        to_detection_response(d)
        for d in detections
        if d.scope_id in allowed_scopes
    ]
    return filtered


@router.get("/coverage", response_model=List[DetectionCoverageResponse])
async def get_coverage(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Evaluate coverage status for MITRE ATT&CK techniques."""
    if current_user.role != "admin":
        if scope_id:
            await check_scope_ownership(db, scope_id, current_user)
            coverage = DetectionCoverageService.calculate_coverage(scope_id)
        else:
            allowed_scopes = await get_allowed_scope_ids(db, current_user)
            coverage = DetectionCoverageService.calculate_coverage(allowed_scopes)
    else:
        coverage = DetectionCoverageService.calculate_coverage(scope_id)

    return coverage


@router.get("/gaps", response_model=List[DetectionCoverageResponse])
async def get_gaps(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve coverage gaps (NOT_COVERED techniques)."""
    coverage = await get_coverage(scope_id=scope_id, db=db, current_user=current_user)
    return [c for c in coverage if c.coverage_status == CoverageStatus.NOT_COVERED]


@router.get("/uncovered", response_model=List[DetectionCoverageResponse])
async def get_uncovered(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Alias endpoint for retrieving uncovered techniques."""
    return await get_gaps(scope_id=scope_id, db=db, current_user=current_user)


@router.get("/summary")
async def get_summary(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve organization or scope specific detection and coverage summary."""
    detections = DetectionService.get_all_detections()

    if current_user.role != "admin":
        if scope_id:
            await check_scope_ownership(db, scope_id, current_user)
            allowed_scopes = {scope_id}
        else:
            allowed_scopes = await get_allowed_scope_ids(db, current_user)

        detections = [d for d in detections if d.scope_id in allowed_scopes]
        coverage_score = DetectionCoverageService.calculate_overall_score(allowed_scopes)
    else:
        if scope_id:
            detections = [d for d in detections if d.scope_id == scope_id]
        coverage_score = DetectionCoverageService.calculate_overall_score(scope_id)

    from src.domain.entities.detection import DetectionStatus

    active_count = sum(1 for d in detections if d.status == DetectionStatus.ACTIVE)
    disabled_count = sum(1 for d in detections if d.status == DetectionStatus.DISABLED)
    deprecated_count = sum(1 for d in detections if d.status == DetectionStatus.DEPRECATED)

    return {
        "total_detections": len(detections),
        "active_detections": active_count,
        "disabled_detections": disabled_count,
        "deprecated_detections": deprecated_count,
        "coverage_score": coverage_score,
    }


@router.get("/{id}", response_model=DetectionResponse)
async def get_detection(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve a specific detection rule by ID."""
    det = DetectionService.get_detection(id)
    if not det:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection rule not found",
        )

    await check_detection_ownership(db, det, current_user)
    return to_detection_response(det)


@router.post("", response_model=DetectionResponse, status_code=status.HTTP_201_CREATED)
async def create_detection(
    req: CreateDetectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Create or synchronize a detection rule (mutating action)."""
    if req.scope_id:
        await check_scope_ownership(db, req.scope_id, current_user)

    # Note: AI Copilot physical blocks are handled via prompt instructions.
    # Standard role access ensures authorization.
    record = DetectionService.create_or_sync_detection(
        name=req.name,
        description=req.description,
        severity=req.severity,
        attack_techniques=req.attack_techniques,
        scope_id=req.scope_id,
    )
    return to_detection_response(record)


@router.post("/{id}/disable", response_model=DetectionResponse)
async def disable_detection(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition a detection rule status to DISABLED."""
    det = DetectionService.get_detection(id)
    if not det:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection rule not found",
        )

    await check_detection_ownership(db, det, current_user)
    record = DetectionService.disable_detection(id)
    return to_detection_response(record)


@router.post("/{id}/deprecate", response_model=DetectionResponse)
async def deprecate_detection(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition a detection rule status to DEPRECATED."""
    det = DetectionService.get_detection(id)
    if not det:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection rule not found",
        )

    await check_detection_ownership(db, det, current_user)
    record = DetectionService.deprecate_detection(id)
    return to_detection_response(record)
