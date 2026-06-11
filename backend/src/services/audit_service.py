import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import AuditLog


async def create_audit_entry(
    db: AsyncSession,
    actor_id: Optional[uuid.UUID],
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    metadata: Optional[dict] = None
) -> AuditLog:
    """Create and persist a system or user audit log entry."""
    db_entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=metadata,
        timestamp=datetime.now(timezone.utc)
    )
    db.add(db_entry)
    await db.commit()
    await db.refresh(db_entry)
    return db_entry
