import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.correlation import CorrelationResponse, RiskResponse
from src.domain.entities.user import StandardResponse
from src.infrastructure.database.models import User
from src.infrastructure.database.session import get_db
from src.services.asset_risk_snapshot_service import AssetRiskSnapshotService
from src.services.asset_service import get_asset_by_id
from src.services.correlation_snapshot_service import CorrelationSnapshotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/assets", tags=["correlations"])


async def check_asset_ownership(db: AsyncSession, asset, current_user: User):
    """Verify that a non-admin user owns the scope containing the asset."""
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


@router.get("/{id}/correlation", response_model=StandardResponse[CorrelationResponse])
async def get_asset_correlation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[CorrelationResponse]:
    """Retrieve details of a specific asset's correlation snapshot."""
    asset = await get_asset_by_id(db, id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    await check_asset_ownership(db, asset, current_user)

    # Retrieve from cache or generate on demand if not cached
    snapshot = CorrelationSnapshotService.get_snapshot(id)
    if snapshot.get("exposure") == "UNKNOWN" and not snapshot.get("ports"):
        snapshot = await CorrelationSnapshotService.generate_snapshot(db, id)

    return StandardResponse(data=CorrelationResponse(**snapshot))


@router.get("/{id}/risk", response_model=StandardResponse[RiskResponse])
async def get_asset_risk_details(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[RiskResponse]:
    """Retrieve computed risk context and exposure details for the asset."""
    asset = await get_asset_by_id(db, id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    await check_asset_ownership(db, asset, current_user)

    # Retrieve from cache or generate on demand if not cached
    snapshot = AssetRiskSnapshotService.get_snapshot(id)
    if snapshot.get("exposure") == "UNKNOWN" and snapshot.get("risk_score") == 0:
        snapshot = await AssetRiskSnapshotService.generate_snapshot(db, id)

    return StandardResponse(data=RiskResponse(**snapshot))
