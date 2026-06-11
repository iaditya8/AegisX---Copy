import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.asset import AssetResponse
from src.domain.entities.scope import ScopeCreate, ScopeResponse, ScopeUpdate
from src.domain.entities.user import StandardResponse
from src.infrastructure.database.models import User
from src.infrastructure.database.session import get_db
from src.services.asset_service import get_assets_by_scope
from src.services.scope_service import (
    create_scope,
    delete_scope,
    get_all_scopes,
    get_scope_by_id,
    get_scopes_by_owner,
    update_scope,
)

router = APIRouter(prefix="/scopes", tags=["scopes"])


def check_scope_ownership(scope, current_user: User):
    """Enforce ownership validation: non-admin users must own the scope."""
    if current_user.role != "admin" and (
        scope.owner_id is None or scope.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permissions to access this scope",
        )


@router.get("", response_model=StandardResponse[List[ScopeResponse]])
async def list_scopes(
    page: int = 1,
    page_size: int = 50,
    owner_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[ScopeResponse]]:
    """List active scopes with pagination.

    Admin gets all (optional owner filter); Operator/Reader gets owned.
    """
    if current_user.role == "admin":
        if owner_id:
            scopes, total = await get_scopes_by_owner(db, owner_id, page, page_size)
        else:
            scopes, total = await get_all_scopes(db, page, page_size)
    else:
        scopes, total = await get_scopes_by_owner(db, current_user.id, page, page_size)

    return StandardResponse(
        data=[ScopeResponse.model_validate(s) for s in scopes],
        meta={"total": total, "page": page, "page_size": page_size},
    )


@router.post(
    "",
    response_model=StandardResponse[ScopeResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_new_scope(
    scope_in: ScopeCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ScopeResponse]:
    """Create a new scope. Admin and Operator roles only."""
    new_scope = await create_scope(
        db, scope_in, owner_id=current_user.id, actor_id=current_user.id
    )
    response.headers["Location"] = f"/api/v1/scopes/{new_scope.id}"
    return StandardResponse(data=ScopeResponse.model_validate(new_scope))


@router.get("/{id}", response_model=StandardResponse[ScopeResponse])
async def get_scope_details(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[ScopeResponse]:
    """Retrieve details for a specific scope.

    Ownership checks applied for non-admins.
    """
    scope = await get_scope_by_id(db, id)
    if not scope:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scope not found"
        )
    check_scope_ownership(scope, current_user)
    return StandardResponse(data=ScopeResponse.model_validate(scope))


@router.put("/{id}", response_model=StandardResponse[ScopeResponse])
async def update_existing_scope(
    id: uuid.UUID,
    scope_in: ScopeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ScopeResponse]:
    """Update an existing scope. Admin and Operator roles only with ownership checks."""
    scope = await get_scope_by_id(db, id)
    if not scope:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scope not found"
        )
    check_scope_ownership(scope, current_user)
    updated = await update_scope(db, id, scope_in, actor_id=current_user.id)
    return StandardResponse(data=ScopeResponse.model_validate(updated))


@router.delete("/{id}", response_model=StandardResponse[bool])
async def delete_existing_scope(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[bool]:
    """Soft delete a scope. Admin and Operator roles only with ownership checks."""
    scope = await get_scope_by_id(db, id)
    if not scope:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scope not found"
        )
    check_scope_ownership(scope, current_user)
    success = await delete_scope(db, id, actor_id=current_user.id)
    return StandardResponse(data=success)


@router.get("/{id}/assets", response_model=StandardResponse[List[AssetResponse]])
async def list_scope_assets(
    id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    host: Optional[str] = None,
    ip: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[AssetResponse]]:
    """List assets within a specific scope. Ownership checks applied."""
    scope = await get_scope_by_id(db, id)
    if not scope:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scope not found"
        )
    check_scope_ownership(scope, current_user)

    assets, total = await get_assets_by_scope(
        db, id, page=page, page_size=page_size, host=host, ip=ip
    )
    return StandardResponse(
        data=[AssetResponse.model_validate(a) for a in assets],
        meta={"total": total, "page": page, "page_size": page_size},
    )
