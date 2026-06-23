import uuid
from datetime import datetime, timezone
from unittest.mock import ANY, MagicMock, patch

import pytest
from httpx import AsyncClient
from src.core.security import create_access_token
from src.domain.entities.asset import AssetCreate, AssetUpdate
from src.infrastructure.database.models import (
    Asset,
    AssetHistory,
    AssetRelationship,
    Scope,
    User,
)
from src.services.asset_service import create_asset, update_asset

# Standard User IDs
ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_A_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER_B_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")

# Scope IDs
SCOPE_A_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
SCOPE_B_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")

# Asset IDs
ASSET_A_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
ASSET_B_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")


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
def mock_user_a() -> User:
    user = User()
    user.id = USER_A_ID
    user.username = "user_a"
    user.role = "operator"
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_user_b() -> User:
    user = User()
    user.id = USER_B_ID
    user.username = "user_b"
    user.role = "operator"
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_scope_a() -> Scope:
    s = Scope()
    s.id = SCOPE_A_ID
    s.owner_id = USER_A_ID
    s.name = "Scope A"
    s.type = "domain"
    s.definition = {"domains": ["a.com"]}
    s.created_at = datetime.now(timezone.utc)
    s.deleted_at = None
    return s


@pytest.fixture
def mock_scope_b() -> Scope:
    s = Scope()
    s.id = SCOPE_B_ID
    s.owner_id = USER_B_ID
    s.name = "Scope B"
    s.type = "domain"
    s.definition = {"domains": ["b.com"]}
    s.created_at = datetime.now(timezone.utc)
    s.deleted_at = None
    return s


@pytest.fixture
def mock_asset_a() -> Asset:
    a = Asset()
    a.id = ASSET_A_ID
    a.scope_id = SCOPE_A_ID
    a.host = "hosta.com"
    a.ip = "192.168.1.1"
    a.asset_type = "host"
    a.metadata_json = {}
    a.first_seen = datetime.now(timezone.utc)
    a.last_seen = datetime.now(timezone.utc)
    a.fingerprint = "fp-a"
    a.deleted_at = None
    return a


@pytest.fixture
def mock_asset_b() -> Asset:
    a = Asset()
    a.id = ASSET_B_ID
    a.scope_id = SCOPE_B_ID
    a.host = "hostb.com"
    a.ip = "192.168.1.2"
    a.asset_type = "host"
    a.metadata_json = {}
    a.first_seen = datetime.now(timezone.utc)
    a.last_seen = datetime.now(timezone.utc)
    a.fingerprint = "fp-b"
    a.deleted_at = None
    return a


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


# --- API Endpoint Integration Tests ---


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.scopes.get_scope_by_id")
@patch("src.api.v1.routers.scopes.get_assets_by_scope")
async def test_list_assets_filtered(
    mock_get_assets: MagicMock,
    mock_get_scope: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_user_a: User,
    mock_scope_a: Scope,
    mock_asset_a: Asset,
) -> None:
    """Test listing assets in a scope with pagination and filters."""
    mock_get_user.return_value = mock_user_a
    mock_get_scope.return_value = mock_scope_a
    mock_get_assets.return_value = ([mock_asset_a], 1)

    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.get(
        f"/api/v1/scopes/{SCOPE_A_ID}/assets?page=1&page_size=10&host=hosta&ip=192.168.1.1",
        headers=headers,
    )

    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert len(res["data"]) == 1
    assert res["data"][0]["host"] == "hosta.com"
    mock_get_assets.assert_called_once_with(
        ANY, SCOPE_A_ID, page=1, page_size=10, host="hosta", ip="192.168.1.1"
    )


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.assets.get_asset_by_id")
@patch("src.api.v1.routers.assets.get_scope_by_id")
async def test_get_asset_details_owner(
    mock_get_scope: MagicMock,
    mock_get_asset: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_user_a: User,
    mock_scope_a: Scope,
    mock_asset_a: Asset,
) -> None:
    """Test retrieving detailed asset fields for an asset owned by the user."""
    mock_get_user.return_value = mock_user_a
    mock_get_asset.return_value = mock_asset_a
    mock_get_scope.return_value = mock_scope_a

    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.get(f"/api/v1/assets/{ASSET_A_ID}", headers=headers)

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["host"] == "hosta.com"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.assets.get_asset_by_id")
@patch("src.api.v1.routers.assets.get_scope_by_id")
async def test_cross_scope_access_denied(
    mock_get_scope: MagicMock,
    mock_get_asset: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_user_b: User,
    mock_scope_a: Scope,
    mock_asset_a: Asset,
) -> None:
    """Cross-Scope Access Test:

    Verify that User B cannot read details of User A's assets.
    """
    mock_get_user.return_value = mock_user_b
    mock_get_asset.return_value = mock_asset_a
    mock_get_scope.return_value = mock_scope_a

    headers = get_auth_header(USER_B_ID, "operator")
    response = await client.get(f"/api/v1/assets/{ASSET_A_ID}", headers=headers)

    # User B does not own Scope A, so it must return 403 Forbidden
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.assets.get_asset_by_id")
@patch("src.api.v1.routers.assets.get_scope_by_id")
@patch("src.api.v1.routers.assets.get_asset_relationships")
async def test_get_asset_relationships(
    mock_get_rel: MagicMock,
    mock_get_scope: MagicMock,
    mock_get_asset: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_user_a: User,
    mock_scope_a: Scope,
    mock_asset_a: Asset,
) -> None:
    """Test retrieving relationships of an asset."""
    mock_get_user.return_value = mock_user_a
    mock_get_asset.return_value = mock_asset_a
    mock_get_scope.return_value = mock_scope_a

    rel = AssetRelationship()
    rel.id = uuid.uuid4()
    rel.source_asset_id = ASSET_A_ID
    rel.target_asset_id = ASSET_B_ID
    rel.relationship_type = "resolves_to"
    rel.metadata_json = {}
    rel.created_at = datetime.now(timezone.utc)
    mock_get_rel.return_value = [rel]

    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.get(
        f"/api/v1/assets/{ASSET_A_ID}/relationships", headers=headers
    )

    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert len(res["data"]) == 1
    assert res["data"][0]["relationship_type"] == "resolves_to"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.assets.get_asset_by_id")
@patch("src.api.v1.routers.assets.get_scope_by_id")
@patch("src.api.v1.routers.assets.get_asset_history")
async def test_get_asset_history_route(
    mock_get_history: MagicMock,
    mock_get_scope: MagicMock,
    mock_get_asset: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_user_a: User,
    mock_scope_a: Scope,
    mock_asset_a: Asset,
) -> None:
    """Test retrieving history revision records for an asset."""
    mock_get_user.return_value = mock_user_a
    mock_get_asset.return_value = mock_asset_a
    mock_get_scope.return_value = mock_scope_a

    h = AssetHistory()
    h.id = uuid.uuid4()
    h.asset_id = ASSET_A_ID
    h.change_type = "create"
    h.old_value = None
    h.new_value = {"host": "hosta.com"}
    h.timestamp = datetime.now(timezone.utc)
    mock_get_history.return_value = [h]

    headers = get_auth_header(USER_A_ID, "operator")
    response = await client.get(f"/api/v1/assets/{ASSET_A_ID}/history", headers=headers)

    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert len(res["data"]) == 1
    assert res["data"][0]["change_type"] == "create"


# --- Service Layer Business Logic & Revision History / Auditing Tests ---


@pytest.mark.asyncio
async def test_create_asset_service(mock_db) -> None:
    """Verify that mock asset writes trigger history persistence and audit logging."""
    asset_in = AssetCreate(
        host="service-asset.com",
        ip="10.0.0.1",
        asset_type="host",
        metadata_json={"os": "linux"},
        fingerprint="fp-service",
    )

    res = await create_asset(
        db=mock_db, asset_in=asset_in, scope_id=SCOPE_A_ID, actor_id=USER_A_ID
    )

    assert res.host == "service-asset.com"
    assert res.scope_id == SCOPE_A_ID
    # Assert DB adds Scope, AssetHistory, and AuditLog entries
    assert mock_db.add.call_count == 3
    # Two commits: one for Asset + history, one for AuditLog
    assert mock_db.commit.call_count == 3


@pytest.mark.asyncio
@patch("src.services.asset_service.get_asset_by_id")
async def test_update_asset_service(mock_get_asset_by_id, mock_db) -> None:
    """Verify that update asset registers field differences in history."""
    existing = Asset()
    existing.id = ASSET_A_ID
    existing.host = "oldhost.com"
    existing.ip = "1.1.1.1"
    existing.asset_type = "host"
    existing.metadata_json = {}
    existing.fingerprint = "old-fp"
    mock_get_asset_by_id.return_value = existing

    asset_update = AssetUpdate(host="newhost.com")
    res = await update_asset(
        db=mock_db, asset_id=ASSET_A_ID, asset_in=asset_update, actor_id=USER_A_ID
    )

    assert res.host == "newhost.com"
    assert mock_db.commit.call_count == 3


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.assets.get_asset_by_id")
async def test_get_asset_parent_scope_deleted(
    mock_get_asset: MagicMock,
    mock_get_user: MagicMock,
    client: AsyncClient,
    mock_admin: User,
) -> None:
    """Verify that accessing an asset of a soft-deleted scope returns 404."""
    mock_get_user.return_value = mock_admin
    mock_get_asset.return_value = None

    headers = get_auth_header(ADMIN_ID, "admin")
    response = await client.get(f"/api/v1/assets/{ASSET_A_ID}", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_get_asset_by_id_parent_scope_deleted_service(mock_db) -> None:
    """Verify that get_asset_by_id returns None if the scope is soft-deleted."""
    asset = Asset()
    asset.id = ASSET_A_ID
    asset.scope_id = SCOPE_A_ID
    asset.deleted_at = None

    mock_asset_result = MagicMock()
    mock_asset_result.scalar_one_or_none.return_value = asset

    mock_scope_result = MagicMock()
    mock_scope_result.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [mock_asset_result, mock_scope_result]

    from src.services.asset_service import get_asset_by_id

    res = await get_asset_by_id(mock_db, ASSET_A_ID)

    assert res is None
