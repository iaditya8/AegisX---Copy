import uuid
from typing import List

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.security import decode_token, hash_api_key
from src.infrastructure.database.models import User
from src.infrastructure.database.session import get_db
from src.services.user_service import get_user_by_id


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    """Retrieve the currently authenticated user from API key or JWT Bearer token."""
    # Check for X-API-Key Header authentication
    api_key = request.headers.get("X-API-Key")
    if api_key:
        hashed_key = hash_api_key(api_key)
        result = await db.execute(
            select(User).where(
                User.api_key_hash == hashed_key, User.deleted_at.is_(None)
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key"
            )
        return user

    # Fallback to JWT Bearer token authentication
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication credentials",
        )

    token = auth_header.split(" ")[1]
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
            )
        user_id = uuid.UUID(user_id_str)
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        )

    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or has been deleted",
        )
    return user


class RoleChecker:
    """RBAC dependency to enforce permitted roles on endpoints."""

    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to perform this action",
            )
        return current_user
