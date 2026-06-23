from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from src.core.security import create_refresh_token, hash_password
from src.infrastructure.database.models import User


@pytest.fixture
def test_user() -> User:
    """Fixture returning a mock User instance."""
    user = User()
    user.id = MagicMock()
    user.id.__str__.return_value = "12345678-1234-1234-1234-123456789abc"
    user.username = "testuser"
    user.role = "operator"
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    user.password_hash = hash_password("supersecretpassword")
    return user


@pytest.mark.asyncio
@patch("src.services.auth_service.get_user_by_username")
async def test_login_success(
    mock_get_user: MagicMock, client: AsyncClient, test_user: User, mock_db: AsyncMock
) -> None:
    """Test login success with correct username and password."""
    mock_get_user.return_value = test_user

    # POST payload
    payload = {"username": "testuser", "password": "supersecretpassword"}
    response = await client.post("/api/v1/auth/token", json=payload)

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert "access_token" in res_data["data"]
    assert "refresh_token" in res_data["data"]
    assert res_data["data"]["token_type"] == "bearer"


@pytest.mark.asyncio
@patch("src.services.auth_service.get_user_by_username")
async def test_login_invalid_password(
    mock_get_user: MagicMock, client: AsyncClient, test_user: User
) -> None:
    """Test login failure with an incorrect password."""
    mock_get_user.return_value = test_user

    payload = {"username": "testuser", "password": "wrongpassword"}
    response = await client.post("/api/v1/auth/token", json=payload)

    assert response.status_code == 401
    res_data = response.json()
    assert res_data["error"]["code"] == "unauthorized"
    assert "Incorrect username or password" in res_data["error"]["message"]


@pytest.mark.asyncio
@patch("src.services.auth_service.get_user_by_username")
async def test_login_nonexistent_user(
    mock_get_user: MagicMock, client: AsyncClient
) -> None:
    """Test login failure for a username that doesn't exist."""
    mock_get_user.return_value = None

    payload = {"username": "ghost", "password": "somepassword"}
    response = await client.post("/api/v1/auth/token", json=payload)

    assert response.status_code == 401
    res_data = response.json()
    assert res_data["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
@patch("src.services.auth_service.get_user_by_id")
async def test_refresh_token_success(
    mock_get_user_by_id: MagicMock, client: AsyncClient, test_user: User
) -> None:
    """Test token refresh rotation using a valid refresh token."""
    mock_get_user_by_id.return_value = test_user

    # Generate a valid refresh token
    ref_token = create_refresh_token(data={"sub": str(test_user.id)})
    payload = {"refresh_token": ref_token}

    response = await client.post("/api/v1/auth/refresh", json=payload)

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert "access_token" in res_data["data"]
    assert "refresh_token" in res_data["data"]


@pytest.mark.asyncio
async def test_refresh_token_invalid(client: AsyncClient) -> None:
    """Test token refresh fails with an invalid signature token."""
    payload = {"refresh_token": "invalid.signature.token"}
    response = await client.post("/api/v1/auth/refresh", json=payload)

    assert response.status_code == 401
    res_data = response.json()
    assert res_data["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_refresh_token_payload_contains_type(test_user: User) -> None:
    """Test that the refresh token payload explicitly contains type=refresh."""
    from src.core.security import decode_token
    from src.services.auth_service import issue_tokens

    tokens = issue_tokens(test_user)
    payload = decode_token(tokens.refresh_token)

    assert payload.get("type") == "refresh"
    assert payload.get("sub") == str(test_user.id)


@pytest.mark.asyncio
async def test_api_key_stored_as_hash(test_user: User, mock_db: AsyncMock) -> None:
    """Test that the API key is generated and stored as a hash in the DB."""
    from src.core.security import hash_api_key
    from src.services.user_service import generate_api_key_for_user

    with patch("src.services.user_service.get_user_by_id", return_value=test_user):
        raw_key = await generate_api_key_for_user(mock_db, test_user.id)

        assert raw_key.startswith("ax_live_")
        # Ensure only the SHA-256 hash is stored, not the raw key
        assert test_user.api_key_hash == hash_api_key(raw_key)
        assert test_user.api_key_hash != raw_key
