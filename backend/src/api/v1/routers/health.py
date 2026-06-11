import logging

import redis.asyncio as async_redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.config import settings
from src.infrastructure.database.session import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/healthz", status_code=status.HTTP_200_OK)
async def healthz() -> dict[str, str]:
    """Liveness check to confirm the API service is up and running."""
    return {"status": "healthy"}


@router.get("/readyz", status_code=status.HTTP_200_OK)
async def readyz(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Readiness check to confirm downstream services (DB, Redis) are healthy."""
    # Check Database connection
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database readiness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is unhealthy",
        )

    # Check Redis connection
    try:
        r = async_redis.from_url(settings.REDIS_URL, socket_timeout=2.0)
        await r.ping()
        await r.close()
    except Exception as e:
        logger.error(f"Redis readiness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis connection is unhealthy",
        )

    return {"status": "ready"}
