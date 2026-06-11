import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from src.core.security import create_access_token, hash_api_key
from src.infrastructure.database.models import User

# Standard user IDs
ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OPERATOR_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
READER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
def mock_admin() -> User:
    user = User()
    user.id = ADMIN_ID
    user.username = "admin_user"
    user.role = "admin"
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    user.password_hash = "somehash"
    user.api_key_hash = None
    return user


@pytest.fixture
def mock_operator() -> User:
    user = User()
    user.id = OPERATOR_ID
    user.username = "operator_user"
    user.role = "operator"
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    user.password_hash = "somehash"
    user.api_key_hash = None
    return user


@pytest.fixture
def mock_reader() -> User:
    user = User()
    user.id = READER_ID
    user.username = "reader_user"
    user.role = "reader"
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    user.password_hash = "somehash"
    user.api_key_hash = None
    return user


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    """Generate headers with a valid signed JWT access token."""
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.users.get_users")
async def test_list_users_as_admin(
    mock_get_users: MagicMock,
    mock_get_user_by_id: MagicMock,
    client: AsyncClient,
    mock_admin: User,
) -> None:
    """Test that admins can list users successfully."""
    mock_get_user_by_id.return_value = mock_admin
    mock_get_users.return_value = ([mock_admin], 1)

    headers = get_auth_header(ADMIN_ID, "admin")
    response = await client.get("/api/v1/users?page=1&page_size=10", headers=headers)

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert len(res_data["data"]) == 1
    assert res_data["data"][0]["username"] == "admin_user"
    assert res_data["meta"]["total"] == 1


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_list_users_as_operator_fails(
    mock_get_user_by_id: MagicMock, client: AsyncClient, mock_operator: User
) -> None:
    """Test that non-admins are forbidden from listing users."""
    mock_get_user_by_id.return_value = mock_operator

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.get("/api/v1/users", headers=headers)

    assert response.status_code == 403
    res_data = response.json()
    assert res_data["error"]["code"] == "forbidden"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.users.create_user")
async def test_create_user_as_admin(
    mock_create: MagicMock,
    mock_get_user_by_id: MagicMock,
    client: AsyncClient,
    mock_admin: User,
    mock_operator: User,
) -> None:
    """Test that admins can create new users."""
    mock_get_user_by_id.return_value = mock_admin
    mock_create.return_value = mock_operator

    headers = get_auth_header(ADMIN_ID, "admin")
    payload = {
        "username": "new_user",
        "display_name": "New User",
        "email": "new@example.com",
        "role": "operator",
        "password": "strongpassword123",
    }
    response = await client.post("/api/v1/users", json=payload, headers=headers)

    assert response.status_code == 201
    assert "Location" in response.headers
    assert response.json()["success"] is True
    assert response.json()["data"]["username"] == "operator_user"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.users.get_user_by_id")
async def test_get_user_self(
    mock_service_get: MagicMock,
    mock_dep_get: MagicMock,
    client: AsyncClient,
    mock_operator: User,
) -> None:
    """Test that a user can retrieve their own details."""
    mock_dep_get.return_value = mock_operator
    mock_service_get.return_value = mock_operator

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.get(f"/api/v1/users/{OPERATOR_ID}", headers=headers)

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["username"] == "operator_user"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_get_user_other_forbidden(
    mock_dep_get: MagicMock, client: AsyncClient, mock_operator: User
) -> None:
    """Test that a non-admin cannot retrieve details of another user."""
    mock_dep_get.return_value = mock_operator

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.get(f"/api/v1/users/{ADMIN_ID}", headers=headers)

    assert response.status_code == 403


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.users.delete_user")
async def test_delete_user_as_admin(
    mock_delete: MagicMock,
    mock_dep_get: MagicMock,
    client: AsyncClient,
    mock_admin: User,
) -> None:
    """Test that admins can soft-delete users."""
    mock_dep_get.return_value = mock_admin
    mock_delete.return_value = True

    headers = get_auth_header(ADMIN_ID, "admin")
    response = await client.delete(f"/api/v1/users/{OPERATOR_ID}", headers=headers)

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"] is True


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.users.generate_api_key_for_user")
async def test_generate_api_key_self(
    mock_gen_key: MagicMock,
    mock_dep_get: MagicMock,
    client: AsyncClient,
    mock_operator: User,
) -> None:
    """Test that a user can generate an API key for themselves."""
    mock_dep_get.return_value = mock_operator
    mock_gen_key.return_value = "ax_live_secretkey123"

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.post(
        f"/api/v1/users/{OPERATOR_ID}/api-key", headers=headers
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["api_key"] == "ax_live_secretkey123"


@pytest.mark.asyncio
async def test_authenticate_via_api_key(
    client: AsyncClient, mock_db: AsyncMock, mock_operator: User
) -> None:
    """Test authentication using the X-API-Key header."""
    raw_key = "ax_live_secretkey123"
    hashed = hash_api_key(raw_key)
    mock_operator.api_key_hash = hashed

    # Mock DB select to return operator when searching by API key hash
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_operator
    mock_db.execute.return_value = mock_result

    # Invoke protected endpoint using X-API-Key
    headers = {"X-API-Key": raw_key}
    response = await client.get(f"/api/v1/users/{OPERATOR_ID}", headers=headers)

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["username"] == "operator_user"
