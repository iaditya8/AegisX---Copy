import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from src.core.security import create_access_token
from src.infrastructure.database.models import Asset, Finding, Scope, User
from src.services.ai_provider import AIProvider
from src.services.ai_provider_registry import AIProviderRegistry

# Standard IDs for testing
ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OPERATOR_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
READER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")

SCOPE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
ASSET_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
FINDING_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


class MockAIProvider(AIProvider):
    def __init__(
        self,
        response_text: str = "{}",
        name: str = "openai",
        version: str = "gpt-4o-mini",
    ):
        self.response_text = response_text
        self.name = name
        self.version = version

    async def generate(self, prompt: str) -> str:
        return self.response_text

    def get_name(self) -> str:
        return self.name

    def get_version(self) -> str:
        return self.version


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
    s.id = SCOPE_ID
    s.owner_id = OPERATOR_ID
    s.name = "Test Scope"
    s.type = "domain"
    s.definition = {"domains": ["test.com"]}
    s.created_at = datetime.now(timezone.utc)
    s.deleted_at = None
    return s


@pytest.fixture
def mock_asset() -> Asset:
    a = Asset()
    a.id = ASSET_ID
    a.scope_id = SCOPE_ID
    a.host = "test.com"
    a.ip = "192.168.1.100"
    a.asset_type = "host"
    a.metadata_json = {}
    a.first_seen = datetime.now(timezone.utc)
    a.last_seen = datetime.now(timezone.utc)
    a.fingerprint = "test-fp"
    a.deleted_at = None
    return a


@pytest.fixture
def mock_finding() -> Finding:
    f = Finding()
    f.id = FINDING_ID
    f.asset_id = ASSET_ID
    f.title = "Test Vulnerability"
    f.description = "Vulnerability description"
    f.severity = "high"
    f.status = "open"
    f.template_id = "test-tpl"
    f.template_name = "Test Tpl"
    f.source_plugin = "nuclei"
    f.first_seen = datetime.now(timezone.utc)
    f.last_seen = datetime.now(timezone.utc)
    f.created_at = datetime.now(timezone.utc)
    f.updated_at = datetime.now(timezone.utc)
    f.fingerprint = "test-finding-fp"
    f.metadata_json = {}
    return f


def get_auth_header(user_id: uuid.UUID, role: str) -> dict:
    token = create_access_token(data={"sub": str(user_id), "roles": [role]})
    return {"Authorization": f"Bearer {token}"}


# --- Unit Tests ---


def test_safety_guardrails_redact_secrets() -> None:
    """Test safety redaction replacing credential keys/values with [REDACTED]."""
    from src.services.ai_guardrails import AIGuardrails

    context = {
        "password": "my_password",
        "api_key": "my_api_key",
        "nested": {"token": "secret_token", "safe": "value"},
        "list": [{"cookie": "session_cookie"}, "Bearer basic_secret_string"],
    }
    sanitized = AIGuardrails.sanitize_context(context)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["safe"] == "value"
    assert sanitized["list"][0]["cookie"] == "[REDACTED]"
    assert sanitized["list"][1] == "[REDACTED]"


def test_invalid_ai_response_rejected() -> None:
    """Validate that non-conforming structures trigger validation errors."""
    from src.services.ai_response_validator import AIResponseValidator

    # Missing required keys (risk_analysis and priority_reasons)
    invalid_response = '{"summary": "Only summary here"}'
    with pytest.raises(ValueError) as excinfo:
        AIResponseValidator.validate_asset_response(invalid_response)
    assert "validation failed" in str(excinfo.value)


def test_provider_registry_returns_openai_provider() -> None:
    """Confirm the provider registry resolves defaults properly."""
    provider = AIProviderRegistry.get_provider()
    assert provider.get_name() == "openai"


def test_rate_limit_enforced() -> None:
    """Verify sliding-window rate limit checks block users who exceed thresholds."""
    from src.services.ai_rate_limit_service import AIRateLimitService

    user_id = uuid.uuid4()
    AIRateLimitService.clear_limits()

    # Operator limit is 250 requests/hour
    for _ in range(250):
        assert AIRateLimitService.check_rate_limit(user_id, "operator") is True
    assert AIRateLimitService.check_rate_limit(user_id, "operator") is False


def test_cache_version_isolation() -> None:
    """Confirm versioned context cache keys isolate cached values."""
    from src.services.ai_cache_service import AICacheService

    asset_id = uuid.uuid4()
    key_v1 = (asset_id, "1.0", "hash")
    key_v2 = (asset_id, "2.0", "hash")

    payload = {"summary": "test"}
    AICacheService.set(key_v1, payload, asset_id=asset_id)

    assert AICacheService.get(key_v1) == payload
    assert AICacheService.get(key_v2) is None


@pytest.mark.asyncio
@patch("src.services.asset_report_service.AssetReportService.generate_asset_report")
async def test_context_version_present(mock_gen_report, mock_db) -> None:
    """Verify Context Builder outputs contain correct CONTEXT_VERSION metadata."""
    from src.services.ai_context_builder import AIContextBuilder

    mock_gen_report.return_value = {
        "asset": {"id": str(ASSET_ID)},
        "exposure": {},
        "risk": {},
        "findings": [],
    }

    context = await AIContextBuilder.build_asset_context(mock_db, ASSET_ID)
    assert context["context_version"] == "1.0"


# --- Integration Tests ---


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.copilot.AssetCopilotService.explain_asset")
async def test_api_explain_asset_admin_allowed(
    mock_service_call,
    mock_get_user,
    client: AsyncClient,
    mock_admin: User,
    mock_db: AsyncMock,
) -> None:
    """Test asset explanation route allowed for Admin."""
    mock_get_user.return_value = mock_admin

    service_response = {
        "success": True,
        "source": "openai",
        "message": "AI explanation generated",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": "Asset summary",
        "risk_analysis": "Risk analysis",
        "priority_reasons": ["Reason 1"],
    }
    mock_service_call.return_value = service_response

    # Setup database mocks for db.get(Asset, ASSET_ID)
    mock_asset = Asset(id=ASSET_ID, scope_id=SCOPE_ID, deleted_at=None)
    mock_db.get = AsyncMock(return_value=mock_asset)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    headers = get_auth_header(ADMIN_ID, "admin")
    response = await client.get(f"/api/v1/copilot/assets/{ASSET_ID}", headers=headers)

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["summary"] == "Asset summary"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
async def test_api_explain_asset_reader_blocked(
    mock_get_user, client: AsyncClient, mock_reader: User
) -> None:
    """Test asset explanation route blocked for Reader (RBAC)."""
    mock_get_user.return_value = mock_reader

    headers = get_auth_header(READER_ID, "reader")
    response = await client.get(f"/api/v1/copilot/assets/{ASSET_ID}", headers=headers)

    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["error"]["message"]


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.copilot.get_scope_by_id")
@patch("src.api.v1.routers.copilot.FindingCopilotService.explain_finding")
async def test_api_explain_finding_owner_check(
    mock_service_call,
    mock_get_scope,
    mock_get_user,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
    mock_finding: Finding,
    mock_db: AsyncMock,
) -> None:
    """Test finding explanation route checks ownership and allows owner operator."""
    mock_get_user.return_value = mock_operator
    mock_get_scope.return_value = mock_scope

    service_response = {
        "success": True,
        "source": "openai",
        "message": "AI explanation generated",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": "Finding summary",
        "impact": "Finding impact",
        "priority": "High",
        "investigation_guidance": "Guidance",
    }
    mock_service_call.return_value = service_response

    mock_asset = Asset(id=ASSET_ID, scope_id=SCOPE_ID, deleted_at=None)

    # Set up mock_db.get side effect to return finding then asset
    mock_db.get = AsyncMock(side_effect=[mock_finding, mock_asset])
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.get(
        f"/api/v1/copilot/findings/{FINDING_ID}", headers=headers
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["summary"] == "Finding summary"


@pytest.mark.asyncio
@patch("src.api.v1.dependencies.auth.get_user_by_id")
@patch("src.api.v1.routers.copilot.get_scope_by_id")
async def test_api_explain_finding_unauthorized_scope_denied(
    mock_get_scope,
    mock_get_user,
    client: AsyncClient,
    mock_operator: User,
    mock_scope: Scope,
    mock_finding: Finding,
    mock_db: AsyncMock,
) -> None:
    """Verify operator trying to explain finding from unowned scope is blocked.

    (Returns 403 Forbidden).
    """
    # Change owner of scope to someone else
    mock_scope.owner_id = uuid.uuid4()
    mock_get_user.return_value = mock_operator
    mock_get_scope.return_value = mock_scope

    mock_asset = Asset(id=ASSET_ID, scope_id=SCOPE_ID, deleted_at=None)
    mock_db.get = AsyncMock(side_effect=[mock_finding, mock_asset])
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    headers = get_auth_header(OPERATOR_ID, "operator")
    response = await client.get(
        f"/api/v1/copilot/findings/{FINDING_ID}", headers=headers
    )

    assert response.status_code == 403
    assert "You do not have permissions" in response.json()["error"]["message"]
