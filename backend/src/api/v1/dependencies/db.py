from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.session import get_db
from src.api.v1.dependencies.auth import get_current_user
from src.infrastructure.database.models import User
import sqlalchemy as sa

async def get_tenant_db(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> AsyncSession:
    """Dependency that returns a database session with RLS context pre-configured."""
    await db.execute(
        sa.text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
        {"tenant_id": str(current_user.tenant_id)}
    )
    return db
