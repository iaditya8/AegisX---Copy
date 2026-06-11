from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_healthz(client: AsyncClient) -> None:
    """Test the liveness check endpoint (/healthz) returns 200 OK."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_readyz_success(client: AsyncClient) -> None:
    """Test the readiness check (/readyz) returns 200
    when all backend services are healthy.
    """
    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        mock_from_url.return_value = mock_redis

        response = await client.get("/readyz")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}
        mock_redis.ping.assert_called_once()
        mock_redis.close.assert_called_once()


@pytest.mark.asyncio
async def test_readyz_db_failure(client: AsyncClient, mock_db: AsyncMock) -> None:
    """Test that /readyz returns 503 Service Unavailable
    when the database query fails.
    """
    mock_db.execute.side_effect = Exception("DB connection error")

    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        mock_from_url.return_value = mock_redis

        response = await client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["error"]["message"] == "Database connection is unhealthy"


@pytest.mark.asyncio
async def test_readyz_redis_failure(client: AsyncClient) -> None:
    """Test that /readyz returns 503 Service Unavailable
    when Redis fails to respond.
    """
    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Redis network timeout")
        mock_from_url.return_value = mock_redis

        response = await client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["error"]["message"] == "Redis connection is unhealthy"
