import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.asset import (
    AssetHistoryResponse,
    AssetRelationshipResponse,
    AssetResponse,
)
from src.domain.entities.user import StandardResponse
from src.infrastructure.database.models import User
from src.infrastructure.database.session import get_db
from src.services.asset_service import (
    get_asset_by_id,
    get_asset_history,
    get_asset_relationships,
)
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/assets", tags=["assets"])


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


@router.get("/{id}", response_model=StandardResponse[AssetResponse])
async def get_asset_details(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[AssetResponse]:
    """Retrieve details of a specific asset. Ownership checks applied."""
    asset = await get_asset_by_id(db, id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    await check_asset_ownership(db, asset, current_user)
    return StandardResponse(data=AssetResponse.model_validate(asset))


@router.get(
    "/{id}/relationships",
    response_model=StandardResponse[List[AssetRelationshipResponse]],
)
async def get_asset_relations(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[AssetRelationshipResponse]]:
    """Retrieve relationships of a specific asset. Ownership checks applied."""
    asset = await get_asset_by_id(db, id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    await check_asset_ownership(db, asset, current_user)

    relations = await get_asset_relationships(db, id)
    return StandardResponse(
        data=[AssetRelationshipResponse.model_validate(r) for r in relations]
    )


@router.get(
    "/{id}/history", response_model=StandardResponse[List[AssetHistoryResponse]]
)
async def get_asset_revision_history(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[AssetHistoryResponse]]:
    """Retrieve revision history of a specific asset. Ownership checks applied."""
    asset = await get_asset_by_id(db, id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    await check_asset_ownership(db, asset, current_user)

    history = await get_asset_history(db, id)
    return StandardResponse(
        data=[AssetHistoryResponse.model_validate(h) for h in history]
    )
