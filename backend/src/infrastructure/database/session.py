from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.core.config import settings

import json
import uuid
from datetime import datetime

def custom_json_serializer(obj):
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

def custom_dumps(obj, **kwargs):
    return json.dumps(obj, default=custom_json_serializer, **kwargs)


from sqlalchemy.pool import NullPool

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    json_serializer=custom_dumps,
    poolclass=NullPool,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


from sqlalchemy import event
from src.core.tenant import get_current_tenant_id

from sqlalchemy.orm import Session

@event.listens_for(Session, "after_begin")
def set_rls_context_after_begin(session, transaction, connection):
    """Automatically set RLS session variable on connection checkout / transaction start."""
    if connection.dialect.name != "postgresql":
        return
    tenant_id = get_current_tenant_id()
    if tenant_id:
        connection.exec_driver_sql(
            f"SELECT set_config('app.current_tenant', '{tenant_id}', true)"
        )



async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency to retrieve an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
