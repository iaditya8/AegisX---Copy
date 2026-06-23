import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from src.core.security import create_access_token
from src.domain.entities.scope import ScopeCreate, ScopeUpdate
from src.infrastructure.database.models import Scope, User
from src.services.scope_service import create_scope, delete_scope, update_scope

# Standard User IDs
ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OPERATOR_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
READER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
OTHER_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


@pytest.fixture
def mock_admin() -> User:
    user = User()
    user.id = ADMIN_ID
    user.username = "admin_user"
    user.role = "admin"
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_operator() -> User:
    user = User()
    user.id = OPERATOR_ID
    user.username = "operator_user"
    user.role = "operator"
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_reader() -> User:
    user = User()
    user.id = READER_ID
    user.username = "reader_user"
    user.role = "reader"
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_scope() -> Scope:
    s = Scope()
    s.id = uuid.UUID("55555555-5555-5555-5555-555555555555")
    s.owner_id = OPERATOR_ID
    s.name = "Test Scope"
    s.type = "domain"
    s.definition = {"domains": ["example.com"]}
    s.created_at = datetime.now(timezone.utc)
    s.deleted_at = None
    s.deleted_by = None
    return s


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


# --- API Endpoint Integration Tests ---


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.scopes.get_all_scopes")
async def test_list_scopes_as_admin(
    mock_get_all: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_admin: User,
    mock_scope: Scope,
) -> None:
    mock_get_user.return_value = mock_admin
    mock_get_all.return_value = ([mock_scope], 1)

    headers = get_auth_header(ADMIN_ID, "admin")
    response = await client.get("/api/v1/scopes", headers=headers)

    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert len(res["data"]) == 1
    assert res["data"][0]["name"] == "Test Scope"
    assert res["meta"]["total"] == 1


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.scopes.get_scopes_by_owner")
async def test_list_scopes_as_operator(
    mock_get_owner: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
) -> None:
    mock_get_user.return_value = mock_operator
    mock_get_owner.return_value = ([mock_scope], 1)

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.get("/api/v1/scopes", headers=headers)

    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert len(res["data"]) == 1
    assert res["data"][0]["owner_id"] == str(OPERATOR_ID)


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.scopes.create_scope")
async def test_create_scope_as_operator(
    mock_create: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
) -> None:
    mock_get_user.return_value = mock_operator
    mock_create.return_value = mock_scope

    payload = {
        "name": "New Scope",
        "type": "domain",
        "definition": {"domains": ["test.com"]},
    }
    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.post("/api/v1/scopes", json=payload, headers=headers)

    assert response.status_code == 201
    assert "Location" in response.headers
    assert response.json()["success"] is True
    assert response.json()["data"]["name"] == "Test Scope"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_create_scope_as_reader_forbidden(
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_reader: User,
) -> None:
    mock_get_user.return_value = mock_reader

    payload = {
        "name": "New Scope",
        "type": "domain",
        "definition": {"domains": ["test.com"]},
    }
    headers = get_auth_header(READER_ID, "reader")
    response = await client.post("/api/v1/scopes", json=payload, headers=headers)

    assert response.status_code == 403


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.scopes.get_scope_by_id")
async def test_get_scope_details_owner(
    mock_get_scope: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
) -> None:
    mock_get_user.return_value = mock_operator
    mock_get_scope.return_value = mock_scope

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.get(f"/api/v1/scopes/{mock_scope.id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["id"] == str(mock_scope.id)


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.scopes.get_scope_by_id")
async def test_get_scope_details_non_owner_forbidden(
    mock_get_scope: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_reader: User,
    mock_scope: Scope,
) -> None:
    # Set reader ID as different from scope owner
    mock_reader.id = OTHER_ID
    mock_get_user.return_value = mock_reader
    mock_get_scope.return_value = mock_scope

    headers = get_auth_header(OTHER_ID, "reader")
    response = await client.get(f"/api/v1/scopes/{mock_scope.id}", headers=headers)

    assert response.status_code == 403


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.scopes.get_scope_by_id")
@patch("src.api.v1.routers.scopes.update_scope")
async def test_update_scope_owner(
    mock_update: MagicMock,
    mock_get_scope: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
) -> None:
    mock_get_user.return_value = mock_operator
    mock_get_scope.return_value = mock_scope

    updated_scope = Scope()
    updated_scope.id = mock_scope.id
    updated_scope.owner_id = mock_scope.owner_id
    updated_scope.name = "Updated Name"
    updated_scope.type = mock_scope.type
    updated_scope.definition = mock_scope.definition
    updated_scope.created_at = mock_scope.created_at
    mock_update.return_value = updated_scope

    payload = {"name": "Updated Name"}
    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.put(
        f"/api/v1/scopes/{mock_scope.id}", json=payload, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Updated Name"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.scopes.get_scope_by_id")
@patch("src.api.v1.routers.scopes.delete_scope")
async def test_delete_scope_owner(
    mock_delete: MagicMock,
    mock_get_scope: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
) -> None:
    mock_get_user.return_value = mock_operator
    mock_get_scope.return_value = mock_scope
    mock_delete.return_value = True

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.delete(f"/api/v1/scopes/{mock_scope.id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"] is True


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.scopes.get_scope_by_id")
async def test_get_scope_not_found(
    mock_get_scope: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_operator: User,
) -> None:
    mock_get_user.return_value = mock_operator
    mock_get_scope.return_value = None

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.get(f"/api/v1/scopes/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404


# --- Service Layer Business Logic & Auditing Tests ---


@pytest.mark.asyncio
async def test_create_scope_service(mock_db) -> None:
    scope_in = ScopeCreate(
        name="Service Scope", type="domain", definition={"domains": ["service.local"]}
    )

    # Execute service call
    res = await create_scope(
        db=mock_db, scope_in=scope_in, owner_id=OPERATOR_ID, actor_id=OPERATOR_ID
    )

    assert res.name == "Service Scope"
    assert res.owner_id == OPERATOR_ID
    # Assert DB add was called for both the Scope and the AuditLog
    assert mock_db.add.call_count == 2

    # Check that commit was called twice (once for Scope, once for AuditLog)
    assert mock_db.commit.call_count == 2


@pytest.mark.asyncio
@patch("src.services.scope_service.get_scope_by_id")
async def test_update_scope_service(mock_get_scope_by_id, mock_db) -> None:
    existing = Scope()
    existing.id = uuid.uuid4()
    existing.name = "Old Name"
    existing.type = "cidr"
    existing.definition = {}
    mock_get_scope_by_id.return_value = existing

    scope_update = ScopeUpdate(name="New Name")
    res = await update_scope(
        db=mock_db, scope_id=existing.id, scope_in=scope_update, actor_id=OPERATOR_ID
    )

    assert res.name == "New Name"
    assert mock_db.commit.call_count == 2  # one for update, one for audit


@pytest.mark.asyncio
@patch("src.services.scope_service.get_scope_by_id")
async def test_delete_scope_service(mock_get_scope_by_id, mock_db) -> None:
    existing = Scope()
    existing.id = uuid.uuid4()
    existing.name = "Delete Scope"
    existing.deleted_at = None
    mock_get_scope_by_id.return_value = existing

    success = await delete_scope(db=mock_db, scope_id=existing.id, actor_id=OPERATOR_ID)

    assert success is True
    assert existing.deleted_at is not None
    assert existing.deleted_by == OPERATOR_ID
    assert mock_db.commit.call_count == 2
