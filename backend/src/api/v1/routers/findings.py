import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.finding import (
    FindingEvidenceResponse,
    FindingResponse,
)
from src.domain.entities.user import StandardResponse
from src.infrastructure.database.models import (
    Asset,
    Finding,
    FindingEvidence,
    Scope,
    User,
)
from src.infrastructure.database.session import get_db
from src.services.finding_service import FindingService

router = APIRouter(prefix="/findings", tags=["findings"])


async def check_finding_ownership(
    db: AsyncSession, finding: Finding, current_user: User
):
    """Enforce ownership validation: non-admin users must own
    the scope containing the asset.
    """
    if current_user.role == "admin":
        return

    asset = await db.get(Asset, finding.asset_id)
    if not asset or not asset.scope_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access this resource",
        )

    scope = await db.get(Scope, asset.scope_id)
    if not scope or scope.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access this resource",
        )


@router.get("", response_model=StandardResponse[List[FindingResponse]])
async def list_findings(
    severity: Optional[str] = None,
    scanner: Optional[str] = None,
    scope_id: Optional[uuid.UUID] = None,
    asset_id: Optional[uuid.UUID] = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[FindingResponse]]:
    """List findings with filters, pagination, and ownership enforcement."""
    # Build query
    q = select(Finding)

    # Apply ownership checks
    if current_user.role != "admin":
        q = q.join(Asset).join(Scope).where(Scope.owner_id == current_user.id)
    else:
        # If admin wants to filter by scope_id or asset_id we join Asset
        if scope_id:
            q = q.join(Asset)

    # Apply filters
    if severity:
        q = q.where(Finding.severity == severity.lower())
    if scanner:
        q = q.where(Finding.source_plugin == scanner)
    if asset_id:
        q = q.where(Finding.asset_id == asset_id)
    if scope_id:
        # If user is admin we joined Asset above, if not it's already joined
        q = q.where(Asset.scope_id == scope_id)

    # Compute total
    count_q = select(func.count()).select_from(q.subquery())
    res_count = await db.execute(count_q)
    total = res_count.scalar() or 0

    # Paginate and sort
    q = q.order_by(Finding.created_at.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)

    res = await db.execute(q)
    findings = res.scalars().all()

    return StandardResponse(
        data=[FindingResponse.model_validate(f) for f in findings],
        meta={"total": total, "page": page, "page_size": page_size},
    )


@router.get("/{id}", response_model=StandardResponse[FindingResponse])
async def get_finding_details(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[FindingResponse]:
    """Retrieve details for a specific finding."""
    finding = await db.get(Finding, id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )

    await check_finding_ownership(db, finding, current_user)
    return StandardResponse(data=FindingResponse.model_validate(finding))


@router.post("/{id}/ack", response_model=StandardResponse[FindingResponse])
async def acknowledge_finding(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[FindingResponse]:
    """Triage finding: transition status to acknowledged."""
    finding = await db.get(Finding, id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )

    await check_finding_ownership(db, finding, current_user)
    updated = await FindingService.update_status(
        db, id, "acknowledged", actor_id=current_user.id
    )
    return StandardResponse(data=FindingResponse.model_validate(updated))


@router.post("/{id}/resolve", response_model=StandardResponse[FindingResponse])
async def resolve_finding(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[FindingResponse]:
    """Manually resolve a finding."""
    finding = await db.get(Finding, id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )

    await check_finding_ownership(db, finding, current_user)
    updated = await FindingService.update_status(
        db, id, "resolved", actor_id=current_user.id
    )
    return StandardResponse(data=FindingResponse.model_validate(updated))


@router.post("/{id}/suppress", response_model=StandardResponse[FindingResponse])
async def suppress_finding(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[FindingResponse]:
    """Mark a finding as false positive/suppressed."""
    finding = await db.get(Finding, id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )

    await check_finding_ownership(db, finding, current_user)
    updated = await FindingService.update_status(
        db, id, "suppressed", actor_id=current_user.id
    )
    return StandardResponse(data=FindingResponse.model_validate(updated))


@router.get(
    "/{id}/evidence", response_model=StandardResponse[List[FindingEvidenceResponse]]
)
async def get_finding_evidences(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[FindingEvidenceResponse]]:
    """Retrieve evidences associated with a finding."""
    finding = await db.get(Finding, id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )

    await check_finding_ownership(db, finding, current_user)

    q = (
        select(FindingEvidence)
        .where(FindingEvidence.finding_id == id)
        .order_by(FindingEvidence.created_at.desc())
    )
    res = await db.execute(q)
    evidences = res.scalars().all()

    return StandardResponse(
        data=[FindingEvidenceResponse.model_validate(e) for e in evidences]
    )
