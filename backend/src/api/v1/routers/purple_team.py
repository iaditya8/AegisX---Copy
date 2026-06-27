import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.user import StandardResponse
from src.domain.entities.purple_team import (
    ExerciseSeverity,
    ExerciseStatus,
    ExerciseType,
    PurpleTeamExerciseResponse,
    ValidationResponse,
    PurpleTeamFindingResponse,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.purple_team_service import PurpleTeamService
from src.services.attack_validation_service import AttackValidationService
from src.services.purple_team_finding_service import PurpleTeamFindingService
from src.services.purple_team_coverage_service import PurpleTeamCoverageService
from src.services.purple_team_drift_service import PurpleTeamDriftService
from src.services.purple_team_snapshot_service import PurpleTeamSnapshotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/purple-team", tags=["purple-team"])


class CreateExerciseRequest(BaseModel):
    name: str
    description: str
    exercise_type: ExerciseType
    severity: ExerciseSeverity
    scope_id: uuid.UUID
    owner: Optional[str] = None
    related_techniques: Optional[List[str]] = None
    related_entities: Optional[List[dict]] = None


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

@router.get("/exercises", response_model=StandardResponse[List[PurpleTeamExerciseResponse]])
async def list_exercises(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[PurpleTeamExerciseResponse]]:
    """List purple team exercises, filtered by scope ownership."""
    exercises = PurpleTeamService.get_all_exercises()
    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        exercises = [e for e in exercises if e.scope_id in allowed_scopes]

    data = [PurpleTeamService.to_response(e) for e in exercises]
    return StandardResponse(data=data)


@router.get("/exercises/active", response_model=StandardResponse[List[PurpleTeamExerciseResponse]])
async def list_active_exercises(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[PurpleTeamExerciseResponse]]:
    """List all active exercises, filtered by scope ownership."""
    exercises = PurpleTeamService.get_all_exercises()
    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        exercises = [e for e in exercises if e.scope_id in allowed_scopes]

    data = [
        PurpleTeamService.to_response(e)
        for e in exercises
        if e.status == ExerciseStatus.ACTIVE
    ]
    return StandardResponse(data=data)


@router.get("/exercises/completed", response_model=StandardResponse[List[PurpleTeamExerciseResponse]])
async def list_completed_exercises(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[PurpleTeamExerciseResponse]]:
    """List all completed exercises, filtered by scope ownership."""
    exercises = PurpleTeamService.get_all_exercises()
    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        exercises = [e for e in exercises if e.scope_id in allowed_scopes]

    data = [
        PurpleTeamService.to_response(e)
        for e in exercises
        if e.status == ExerciseStatus.COMPLETED
    ]
    return StandardResponse(data=data)


@router.get("/exercises/{exercise_id}", response_model=StandardResponse[PurpleTeamExerciseResponse])
async def get_exercise(
    exercise_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[PurpleTeamExerciseResponse]:
    """Retrieve specific exercise details, validating scope ownership."""
    exercise = PurpleTeamService.get_exercise(exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found",
        )

    await check_scope_ownership(db, exercise.scope_id, current_user)
    return StandardResponse(data=PurpleTeamService.to_response(exercise))


@router.get("/validations", response_model=StandardResponse[List[ValidationResponse]])
async def list_validations(
    exercise_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[ValidationResponse]]:
    """Retrieve validations, optionally filtered by exercise ID."""
    if exercise_id:
        exercise = PurpleTeamService.get_exercise(exercise_id)
        if not exercise:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exercise not found",
            )
        await check_scope_ownership(db, exercise.scope_id, current_user)
        validations = AttackValidationService.get_exercise_validations(exercise_id)
    else:
        validations = AttackValidationService.get_all_validations()
        if current_user.role != "admin":
            allowed_scopes = await get_allowed_scope_ids(db, current_user)
            validations = [
                v for v in validations
                if PurpleTeamService.get_exercise(v.exercise_id)
                and PurpleTeamService.get_exercise(v.exercise_id).scope_id in allowed_scopes
            ]

    data = [
        ValidationResponse(
            validation_id=v.validation_id,
            exercise_id=v.exercise_id,
            technique_id=v.technique_id,
            validation_status=v.validation_status,
            expected_detection=v.expected_detection,
            actual_detection=v.actual_detection,
            coverage_gap=v.coverage_gap,
            created_at=v.created_at,
            updated_at=v.updated_at,
        )
        for v in validations
    ]
    return StandardResponse(data=data)


@router.get("/findings", response_model=StandardResponse[List[PurpleTeamFindingResponse]])
async def list_findings(
    exercise_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[PurpleTeamFindingResponse]]:
    """Retrieve findings, optionally filtered by exercise ID."""
    if exercise_id:
        exercise = PurpleTeamService.get_exercise(exercise_id)
        if not exercise:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exercise not found",
            )
        await check_scope_ownership(db, exercise.scope_id, current_user)
        findings = PurpleTeamFindingService.get_findings(exercise_id)
    else:
        findings = PurpleTeamFindingService.get_all_findings()
        if current_user.role != "admin":
            allowed_scopes = await get_allowed_scope_ids(db, current_user)
            findings = [
                f for f in findings
                if PurpleTeamService.get_exercise(f.exercise_id)
                and PurpleTeamService.get_exercise(f.exercise_id).scope_id in allowed_scopes
            ]

    return StandardResponse(data=findings)


@router.get("/coverage", response_model=StandardResponse[Dict[str, float]])
async def get_coverage(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict[str, float]]:
    """Retrieve coverage analytics, filtered by scope ownership."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Non-admin users must specify a scope they own",
        )

    coverage = PurpleTeamCoverageService.calculate_coverage(scope_id)
    return StandardResponse(data=coverage)


@router.get("/drift", response_model=StandardResponse[Dict[str, str]])
async def check_drift(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict[str, str]]:
    """Perform drift detection against previous snapshot."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Non-admin users must specify a scope they own",
        )

    prev_snap = PurpleTeamSnapshotService._snapshots.get(scope_id)
    await PurpleTeamDriftService.check_drift(db, scope_id=scope_id, prev_snapshot=prev_snap)
    PurpleTeamSnapshotService.generate_snapshot(scope_id)

    return StandardResponse(data={"status": "drift check complete"})


@router.get("/summary", response_model=StandardResponse[Dict[str, int]])
async def get_summary(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict[str, int]]:
    """Retrieve summary counts, filtered by scope ownership."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    elif current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Non-admin users must specify a scope they own",
        )

    snap = PurpleTeamSnapshotService.get_snapshot(scope_id)
    return StandardResponse(data=snap["summary"])


@router.post("/exercises", response_model=StandardResponse[PurpleTeamExerciseResponse], status_code=status.HTTP_201_CREATED)
async def create_exercise(
    req: CreateExerciseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[PurpleTeamExerciseResponse]:
    """Create or synchronize a Purple Team Exercise."""
    await check_scope_ownership(db, req.scope_id, current_user)

    try:
        ex = PurpleTeamService.create_or_sync_exercise(
            name=req.name,
            description=req.description,
            exercise_type=req.exercise_type,
            severity=req.severity,
            scope_id=req.scope_id,
            owner=req.owner,
            related_techniques=req.related_techniques,
            related_entities=req.related_entities,
        )
        PurpleTeamSnapshotService.generate_snapshot(req.scope_id)
        return StandardResponse(data=PurpleTeamService.to_response(ex))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/exercises/{exercise_id}/activate", response_model=StandardResponse[PurpleTeamExerciseResponse])
async def activate_exercise(
    exercise_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[PurpleTeamExerciseResponse]:
    """Transition exercise status to ACTIVE."""
    exercise = PurpleTeamService.get_exercise(exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found",
        )

    await check_scope_ownership(db, exercise.scope_id, current_user)

    try:
        updated = PurpleTeamService.activate_exercise(exercise_id, owner=current_user.username)
        # Run validation
        await AttackValidationService.validate_exercise_techniques(db, exercise_id)
        PurpleTeamSnapshotService.generate_snapshot(exercise.scope_id)
        return StandardResponse(data=PurpleTeamService.to_response(updated))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/exercises/{exercise_id}/review", response_model=StandardResponse[PurpleTeamExerciseResponse])
async def review_exercise(
    exercise_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[PurpleTeamExerciseResponse]:
    """Transition exercise status to UNDER_REVIEW."""
    exercise = PurpleTeamService.get_exercise(exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found",
        )

    await check_scope_ownership(db, exercise.scope_id, current_user)

    try:
        updated = PurpleTeamService.review_exercise(exercise_id)
        PurpleTeamSnapshotService.generate_snapshot(exercise.scope_id)
        return StandardResponse(data=PurpleTeamService.to_response(updated))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/exercises/{exercise_id}/complete", response_model=StandardResponse[PurpleTeamExerciseResponse])
async def complete_exercise(
    exercise_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[PurpleTeamExerciseResponse]:
    """Transition exercise status to COMPLETED."""
    exercise = PurpleTeamService.get_exercise(exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found",
        )

    await check_scope_ownership(db, exercise.scope_id, current_user)

    try:
        updated = PurpleTeamService.complete_exercise(exercise_id)
        PurpleTeamSnapshotService.generate_snapshot(exercise.scope_id)
        return StandardResponse(data=PurpleTeamService.to_response(updated))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/exercises/{exercise_id}/close", response_model=StandardResponse[PurpleTeamExerciseResponse])
async def close_exercise(
    exercise_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[PurpleTeamExerciseResponse]:
    """Transition exercise status to CLOSED (terminal state)."""
    exercise = PurpleTeamService.get_exercise(exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found",
        )

    await check_scope_ownership(db, exercise.scope_id, current_user)

    try:
        updated = PurpleTeamService.close_exercise(exercise_id)
        PurpleTeamSnapshotService.generate_snapshot(exercise.scope_id)
        return StandardResponse(data=PurpleTeamService.to_response(updated))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
