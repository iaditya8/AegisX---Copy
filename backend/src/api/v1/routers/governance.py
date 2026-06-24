import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.governance import (
    GovernanceSnapshotResponse,
    RiskAcceptanceResponse,
)
from src.domain.entities.user import StandardResponse
from src.infrastructure.database.models import Asset, Finding, User
from src.infrastructure.database.session import get_db
from src.services.governance_service import GovernanceService
from src.services.governance_snapshot_service import GovernanceSnapshotService
from src.services.risk_acceptance_service import (
    RiskAcceptanceRecord,
    RiskAcceptanceService,
)
from src.services.scope_service import get_scope_by_id

router = APIRouter(tags=["governance"])


# --- Request Models ---


class AcceptRiskRequest(BaseModel):
    asset_id: uuid.UUID
    finding_id: Optional[uuid.UUID] = None
    recommendation_id: Optional[uuid.UUID] = None
    recommendation_fingerprint: str
    approved_by: str
    reason: str


class RevokeRiskRequest(BaseModel):
    acceptance_id: uuid.UUID


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


def to_acceptance_response(r: RiskAcceptanceRecord) -> RiskAcceptanceResponse:
    """Map RiskAcceptanceRecord to Pydantic RiskAcceptanceResponse."""
    return RiskAcceptanceResponse(
        acceptance_id=r.acceptance_id,
        asset_id=r.asset_id,
        finding_id=r.finding_id,
        recommendation_id=r.recommendation_id,
        recommendation_fingerprint=r.recommendation_fingerprint,
        approved_by=r.approved_by,
        approved_at=r.approved_at,
        expiration_date=r.expiration_date,
        status=r.status,
        reason=r.reason,
    )


# --- API Routes ---


@router.get(
    "/governance/assets/{id}",
    response_model=StandardResponse[str],
)
async def get_asset_governance_status(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[str]:
    """Retrieve the governance status of a specific asset."""
    asset = await db.get(Asset, id)
    if not asset or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )
    await check_asset_ownership(db, asset, current_user)
    status_val = await GovernanceService.evaluate_asset_governance(db, id)
    return StandardResponse[str](
        success=True,
        message="Asset governance status retrieved",
        data=status_val.value,
    )


@router.get(
    "/governance/findings/{id}",
    response_model=StandardResponse[str],
)
async def get_finding_governance_status(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[str]:
    """Retrieve the governance status of a specific finding."""
    finding = await db.get(Finding, id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found",
        )
    asset = await db.get(Asset, finding.asset_id)
    if not asset or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated asset not found",
        )
    await check_asset_ownership(db, asset, current_user)
    status_val = await GovernanceService.evaluate_finding_governance(db, id)
    return StandardResponse[str](
        success=True,
        message="Finding governance status retrieved",
        data=status_val.value,
    )


@router.get(
    "/governance/summary",
    response_model=StandardResponse[GovernanceSnapshotResponse],
)
async def get_governance_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[GovernanceSnapshotResponse]:
    """Retrieve platform-wide governance summary snapshot."""
    snapshot = await GovernanceSnapshotService.get_snapshot(db)
    return StandardResponse[GovernanceSnapshotResponse](
        success=True,
        message="Governance summary retrieved",
        data=GovernanceSnapshotResponse(**snapshot),
    )


@router.get(
    "/governance/non-compliant-assets",
    response_model=StandardResponse[List[Any]],
)
async def list_non_compliant_assets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[Any]]:
    """Retrieve non-compliant assets, filtered by scope ownership for non-admin operators."""
    assets = await GovernanceService.get_non_compliant_assets(db)
    filtered = []
    for asset in assets:
        try:
            await check_asset_ownership(db, asset, current_user)
            filtered.append(
                {
                    "id": str(asset.id),
                    "host": asset.host,
                    "ip": asset.ip,
                    "asset_type": asset.asset_type,
                }
            )
        except HTTPException:
            # Skip assets user does not own
            continue
    return StandardResponse[List[Any]](
        success=True,
        message="Non-compliant assets retrieved",
        data=filtered,
    )


@router.get(
    "/governance/non-compliant-findings",
    response_model=StandardResponse[List[Any]],
)
async def list_non_compliant_findings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[Any]]:
    """Retrieve non-compliant findings, filtered by scope ownership for non-admin operators."""
    findings = await GovernanceService.get_non_compliant_findings(db)
    filtered = []
    for f in findings:
        asset = await db.get(Asset, f.asset_id)
        if not asset or asset.deleted_at is not None:
            continue
        try:
            await check_asset_ownership(db, asset, current_user)
            filtered.append(
                {
                    "id": str(f.id),
                    "asset_id": str(f.asset_id),
                    "title": f.title,
                    "severity": f.severity,
                    "status": f.status,
                }
            )
        except HTTPException:
            continue
    return StandardResponse[List[Any]](
        success=True,
        message="Non-compliant findings retrieved",
        data=filtered,
    )


@router.get(
    "/governance/accepted-risks",
    response_model=StandardResponse[List[RiskAcceptanceResponse]],
)
async def list_accepted_risks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[RiskAcceptanceResponse]]:
    """Retrieve active risk acceptances, filtered by scope ownership."""
    acceptances = RiskAcceptanceService.get_active_acceptances()
    filtered = []
    for a in acceptances:
        asset = await db.get(Asset, a.asset_id)
        if not asset or asset.deleted_at is not None:
            continue
        try:
            await check_asset_ownership(db, asset, current_user)
            filtered.append(to_acceptance_response(a))
        except HTTPException:
            continue
    return StandardResponse[List[RiskAcceptanceResponse]](
        success=True,
        message="Active risk acceptances retrieved",
        data=filtered,
    )


@router.post(
    "/governance/accept-risk",
    response_model=StandardResponse[RiskAcceptanceResponse],
)
async def accept_risk(
    req: AcceptRiskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[RiskAcceptanceResponse]:
    """Formally accept risk for a recommendation fingerprint (Admin only)."""
    record = await RiskAcceptanceService.accept_risk(
        db=db,
        asset_id=req.asset_id,
        finding_id=req.finding_id,
        recommendation_id=req.recommendation_id,
        recommendation_fingerprint=req.recommendation_fingerprint,
        approved_by=req.approved_by,
        reason=req.reason,
        actor_id=current_user.id,
    )
    return StandardResponse[RiskAcceptanceResponse](
        success=True,
        message="Risk accepted successfully",
        data=to_acceptance_response(record),
    )


@router.post(
    "/governance/revoke-risk",
    response_model=StandardResponse[RiskAcceptanceResponse],
)
async def revoke_risk(
    req: RevokeRiskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[RiskAcceptanceResponse]:
    """Revoke a risk acceptance policy (Admin only)."""
    record = await RiskAcceptanceService.revoke_risk(
        db=db,
        acceptance_id=req.acceptance_id,
        actor_id=current_user.id,
    )
    return StandardResponse[RiskAcceptanceResponse](
        success=True,
        message="Risk acceptance revoked",
        data=to_acceptance_response(record),
    )
