import uuid
from datetime import datetime, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.config import settings
from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from src.domain.entities.user import TokenResponse
from src.infrastructure.database.models import User
from src.services.user_service import get_user_by_id, get_user_by_username


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> Optional[User]:
    """Verify credentials, update last login, and return authenticated user."""
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None

    # Update last login timestamp
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    return user


def issue_tokens(user: User) -> TokenResponse:
    """Generate signed access and refresh tokens for a user."""
    user_id_str = str(user.id)
    access_token = create_access_token(data={"sub": user_id_str, "roles": [user.role]})
    refresh_token = create_refresh_token(data={"sub": user_id_str})
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=refresh_token,
    )


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> TokenResponse:
    """Validate refresh token and issue a new set of tokens."""
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
            )
        user_id = uuid.UUID(user_id_str)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user identifier"
        )

    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deleted"
        )

    return issue_tokens(user)
