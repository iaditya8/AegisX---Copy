import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker, get_current_user
from src.domain.entities.user import (
    APIKeyResponse,
    StandardResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from src.infrastructure.database.models import User
from src.infrastructure.database.session import get_db
from src.services.user_service import (
    create_user,
    delete_user,
    generate_api_key_for_user,
    get_user_by_id,
    get_users,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=StandardResponse[List[UserResponse]])
async def list_users(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[List[UserResponse]]:
    """List active users with offset pagination. Admins only."""
    users, total = await get_users(db, page, page_size)
    return StandardResponse(
        data=users, meta={"total": total, "page": page, "page_size": page_size}
    )


@router.post(
    "",
    response_model=StandardResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_new_user(
    user_in: UserCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[UserResponse]:
    """Create a new user record. Admins only."""
    new_user = await create_user(db, user_in)
    response.headers["Location"] = f"/api/v1/users/{new_user.id}"
    return StandardResponse(data=new_user)


@router.get("/me", response_model=StandardResponse[UserResponse])
async def get_current_user_details(
    current_user: User = Depends(get_current_user),
) -> StandardResponse[UserResponse]:
    """Retrieve details for the currently authenticated user."""
    return StandardResponse(data=current_user)


@router.get("/{user_id}", response_model=StandardResponse[UserResponse])
async def get_user_details(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StandardResponse[UserResponse]:
    """Retrieve details for a specific user. Accessible by admins or the owner."""
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access this user resource",
        )
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return StandardResponse(data=user)


@router.put("/{user_id}", response_model=StandardResponse[UserResponse])
async def update_existing_user(
    user_id: uuid.UUID,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StandardResponse[UserResponse]:
    """Update details for a user. Accessible by admins or the owner."""
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to modify this user resource",
        )
    updated = await update_user(db, user_id, user_in)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return StandardResponse(data=updated)


@router.delete("/{user_id}", response_model=StandardResponse[bool])
async def delete_existing_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[bool]:
    """Soft delete a user. Admins only."""
    success = await delete_user(db, user_id, deleted_by=admin_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return StandardResponse(data=True)


@router.post("/{user_id}/api-key", response_model=StandardResponse[APIKeyResponse])
async def generate_user_api_key(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StandardResponse[APIKeyResponse]:
    """Generate or rotate a new API key for a user.
    Accessible by admins or the owner.
    """
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage API keys for this user",
        )
    raw_key = await generate_api_key_for_user(db, user_id)
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return StandardResponse(data=APIKeyResponse(api_key=raw_key))
