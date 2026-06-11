from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.user import (
    LoginRequest,
    StandardResponse,
    TokenRefreshRequest,
    TokenResponse,
)
from src.infrastructure.database.session import get_db
from src.services.auth_service import (
    authenticate_user,
    issue_tokens,
    refresh_access_token,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/token", response_model=StandardResponse[TokenResponse])
async def login(
    login_data: LoginRequest, db: AsyncSession = Depends(get_db)
) -> StandardResponse[TokenResponse]:
    """Exchange username and password credentials for an access and refresh token."""
    user = await authenticate_user(db, login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    tokens = issue_tokens(user)
    return StandardResponse(data=tokens)


@router.post("/refresh", response_model=StandardResponse[TokenResponse])
async def refresh_token(
    refresh_data: TokenRefreshRequest, db: AsyncSession = Depends(get_db)
) -> StandardResponse[TokenResponse]:
    """Exchange a valid refresh token for a new set of tokens (access + refresh)."""
    tokens = await refresh_access_token(db, refresh_data.refresh_token)
    return StandardResponse(data=tokens)
