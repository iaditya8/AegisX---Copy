import os
import sys
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

# Add backend/ to the Python import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.infrastructure.database.session import get_db
from src.main import app


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock for SQLAlchemy AsyncSession to avoid database dependencies in unit tests."""
    mock = AsyncMock()
    mock_result = MagicMock()
    mock.execute.return_value = mock_result
    return mock


@pytest.fixture
async def client(mock_db: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client fixture with overridden database dependency."""

    # Override get_db dependency with mock_db
    async def override_get_db() -> AsyncGenerator[AsyncMock, None]:
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    # Clear dependency overrides after each test
    app.dependency_overrides.clear()
