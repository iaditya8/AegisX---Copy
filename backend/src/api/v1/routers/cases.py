import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.case import (
    CaseHistoryEntry,
    CaseResponse,
    CaseSeverity,
    CaseStatus,
    ChainOfCustodyEntry,
    EvidenceResponse,
    EvidenceStatus,
)
from src.infrastructure.database.models import Asset, Scope, User
from src.infrastructure.database.session import get_db
from src.services.case_evidence_correlation_service import CaseEvidenceCorrelationService
from src.services.case_history_service import CaseHistoryService
from src.services.case_service import CaseRecord, CaseService
from src.services.custody_service import CustodyService
from src.services.evidence_service import EvidenceRecord, EvidenceService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/cases", tags=["cases"])


class AssignCaseRequest(BaseModel):
    owner_id: Optional[uuid.UUID] = None


class CollectEvidenceRequest(BaseModel):
    source_entity: str
    source_id: uuid.UUID
    raw_data: str
    integrity_hash: Optional[str] = None


class TransferEvidenceRequest(BaseModel):
    evidence_id: uuid.UUID
    new_case_id: uuid.UUID
    notes: Optional[str] = ""


# --- Helper Checks ---


async def get_allowed_asset_ids(db: AsyncSession, current_user: User) -> Optional[set]:
    """Retrieve allowed asset IDs for non-admin users based on scope ownership."""
    if current_user.role == "admin":
        return None

    q_scopes = select(Scope).where(
        Scope.owner_id == current_user.id, Scope.deleted_at.is_(None)
    )
    res_scopes = await db.execute(q_scopes)
    scopes = res_scopes.scalars().all()
    scope_ids = {s.id for s in scopes}

    if not scope_ids:
        return set()

    q_assets = select(Asset.id).where(
        Asset.scope_id.in_(scope_ids), Asset.deleted_at.is_(None)
    )
    res_assets = await db.execute(q_assets)
    return set(res_assets.scalars().all())


async def check_case_ownership(
    db: AsyncSession, case: CaseRecord, current_user: User
) -> None:
    """Enforce scope ownership check for non-admin operators on a specific case."""
    if current_user.role == "admin":
        return

    if not case.asset_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permissions to access this case",
        )

    for asset_id in case.asset_ids:
        asset = await db.get(Asset, asset_id)
        if not asset or asset.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Linked asset not found",
            )

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


def to_case_response(c: CaseRecord) -> CaseResponse:
    """Map CaseRecord to Pydantic CaseResponse."""
    return CaseResponse(
        case_id=c.case_id,
        case_fingerprint=c.case_fingerprint,
        title=c.title,
        description=c.description,
        severity=c.severity,
        status=c.status,
        owner=c.owner,
        created_at=c.created_at,
        updated_at=c.updated_at,
        incident_ids=c.incident_ids,
    )


def to_evidence_response(ev: EvidenceRecord) -> EvidenceResponse:
    """Map EvidenceRecord to Pydantic EvidenceResponse."""
    return EvidenceResponse(
        evidence_id=ev.evidence_id,
        case_id=ev.case_id,
        source_entity=ev.source_entity,
        source_id=ev.source_id,
        integrity_hash=ev.integrity_hash,
        status=ev.status,
        collected_by=ev.collected_by,
        collected_at=ev.collected_at,
    )


# --- API Routes ---


@router.get("", response_model=List[CaseResponse])
async def list_cases(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all cases, applying scope-filtering for non-admins."""
    cases = CaseService.get_all_cases()
    if current_user.role == "admin":
        return [to_case_response(c) for c in cases]

    allowed_asset_ids = await get_allowed_asset_ids(db, current_user)
    filtered = []
    for c in cases:
        if not c.asset_ids:
            continue
        if all(aid in allowed_asset_ids for aid in c.asset_ids):
            filtered.append(to_case_response(c))
    return filtered


@router.get("/{id}", response_model=CaseResponse)
async def get_case(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve a specific case by ID."""
    case = CaseService.get_case(id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {id} not found",
        )
    await check_case_ownership(db, case, current_user)
    return to_case_response(case)


@router.post("/{id}/assign", response_model=CaseResponse)
async def assign_case(
    id: uuid.UUID,
    req: AssignCaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Assign case to a user."""
    case = CaseService.get_case(id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {id} not found",
        )
    await check_case_ownership(db, case, current_user)
    try:
        updated = await CaseService.assign_case(
            db=db, case_id=id, owner_id=req.owner_id, actor_id=current_user.id
        )
        return to_case_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{id}/activate", response_model=CaseResponse)
async def activate_case(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition case to ACTIVE."""
    case = CaseService.get_case(id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {id} not found",
        )
    await check_case_ownership(db, case, current_user)
    try:
        updated = await CaseService.transition_status(
            db=db, case_id=id, new_status=CaseStatus.ACTIVE, actor_id=current_user.id
        )
        return to_case_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{id}/review", response_model=CaseResponse)
async def review_case(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition case to UNDER_REVIEW."""
    case = CaseService.get_case(id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {id} not found",
        )
    await check_case_ownership(db, case, current_user)
    try:
        updated = await CaseService.transition_status(
            db=db, case_id=id, new_status=CaseStatus.UNDER_REVIEW, actor_id=current_user.id
        )
        return to_case_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{id}/resolve", response_model=CaseResponse)
async def resolve_case(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition case to RESOLVED."""
    case = CaseService.get_case(id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {id} not found",
        )
    await check_case_ownership(db, case, current_user)
    try:
        updated = await CaseService.transition_status(
            db=db, case_id=id, new_status=CaseStatus.RESOLVED, actor_id=current_user.id
        )
        return to_case_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{id}/close", response_model=CaseResponse)
async def close_case(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transition case to CLOSED."""
    case = CaseService.get_case(id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {id} not found",
        )
    await check_case_ownership(db, case, current_user)
    try:
        updated = await CaseService.transition_status(
            db=db, case_id=id, new_status=CaseStatus.CLOSED, actor_id=current_user.id
        )
        return to_case_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Evidence Endpoints ---


@router.get("/{id}/evidence", response_model=List[EvidenceResponse])
async def list_case_evidence(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all evidence associated with a case."""
    case = CaseService.get_case(id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {id} not found",
        )
    await check_case_ownership(db, case, current_user)

    correlation = CaseEvidenceCorrelationService.get_correlated_evidence(id, case.incident_ids)
    return [to_evidence_response(ev) for ev in correlation["case_evidence"]]


@router.post("/{id}/evidence", response_model=EvidenceResponse)
async def collect_evidence(
    id: uuid.UUID,
    req: CollectEvidenceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Collect evidence and attach it to a case."""
    case = CaseService.get_case(id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {id} not found",
        )
    await check_case_ownership(db, case, current_user)

    try:
        record = EvidenceService.add_evidence(
            case_id=id,
            source_entity=req.source_entity,
            source_id=req.source_id,
            collected_by=current_user.id,
            raw_data=req.raw_data,
            integrity_hash=req.integrity_hash,
        )
        return to_evidence_response(record)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{id}/custody", response_model=List[ChainOfCustodyEntry])
async def list_custody_timeline(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve custody timeline entries for all evidence in a case."""
    case = CaseService.get_case(id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {id} not found",
        )
    await check_case_ownership(db, case, current_user)

    correlation = CaseEvidenceCorrelationService.get_correlated_evidence(id, case.incident_ids)
    custody_entries = []
    for ev in correlation["case_evidence"]:
        custody_entries.extend(CustodyService.get_custody(ev.evidence_id))

    # Sort entries by timestamp
    custody_entries.sort(key=lambda x: x.timestamp)
    return custody_entries


@router.post("/{id}/transfer", response_model=EvidenceResponse)
async def transfer_evidence(
    id: uuid.UUID,
    req: TransferEvidenceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Transfer evidence to another case."""
    evidence = EvidenceService.get_evidence_by_id(req.evidence_id)
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with ID {req.evidence_id} not found",
        )

    source_case = CaseService.get_case(evidence.case_id)
    target_case = CaseService.get_case(req.new_case_id)

    if not source_case or not target_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source or target case not found",
        )

    await check_case_ownership(db, source_case, current_user)
    await check_case_ownership(db, target_case, current_user)

    try:
        updated = EvidenceService.transfer_evidence(
            evidence_id=req.evidence_id,
            new_case_id=req.new_case_id,
            actor_id=current_user.id,
            notes=req.notes,
        )
        return to_evidence_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{id}/timeline", response_model=List[CaseHistoryEntry])
async def get_case_timeline(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve history timeline entries for a case."""
    case = CaseService.get_case(id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {id} not found",
        )
    await check_case_ownership(db, case, current_user)

    history = CaseHistoryService.get_history(id)
    sorted_history = sorted(history, key=lambda x: x.timestamp)
    return sorted_history


@router.post("/{id}/evidence/{evidence_id}/verify")
async def verify_evidence_endpoint(
    id: uuid.UUID,
    evidence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Verify forensic integrity of a piece of evidence."""
    case = CaseService.get_case(id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    await check_case_ownership(db, case, current_user)

    evidence = EvidenceService.get_evidence_by_id(evidence_id)
    if not evidence or evidence.case_id != id:
        raise HTTPException(status_code=404, detail="Evidence not found on this case")

    try:
        passed = await EvidenceService.verify_evidence_integrity(
            db, evidence_id, current_user.id
        )
        return {"integrity_verified": passed}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{id}/evidence/{evidence_id}/archive", response_model=EvidenceResponse)
async def archive_evidence_endpoint(
    id: uuid.UUID,
    evidence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Archive a piece of evidence."""
    case = CaseService.get_case(id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    await check_case_ownership(db, case, current_user)

    evidence = EvidenceService.get_evidence_by_id(evidence_id)
    if not evidence or evidence.case_id != id:
        raise HTTPException(status_code=404, detail="Evidence not found on this case")

    try:
        updated = EvidenceService.archive_evidence(evidence_id, current_user.id)
        return to_evidence_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
