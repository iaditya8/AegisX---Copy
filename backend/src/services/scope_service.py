import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.scope import ScopeCreate, ScopeUpdate
from src.infrastructure.database.models import Scope
from src.services.audit_service import create_audit_entry


async def get_scope_by_id(db: AsyncSession, scope_id: uuid.UUID) -> Optional[Scope]:
    """Retrieve an active scope by ID."""
    result = await db.execute(
        select(Scope).where(Scope.id == scope_id, Scope.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()

async def get_scopes_by_owner(
    db: AsyncSession, owner_id: uuid.UUID, page: int = 1, page_size: int = 50
) -> Tuple[List[Scope], int]:
    """Retrieve active scopes owned by a specific user with pagination."""
    offset = (page - 1) * page_size
    query = (
        select(Scope)
        .where(Scope.owner_id == owner_id, Scope.deleted_at.is_(None))
        .order_by(Scope.created_at.desc())
    )
    count_query = select(func.count(Scope.id)).where(
        Scope.owner_id == owner_id, Scope.deleted_at.is_(None)
    )

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    result = await db.execute(query.offset(offset).limit(page_size))
    scopes = list(result.scalars().all())
    return scopes, total

async def get_all_scopes(
    db: AsyncSession, page: int = 1, page_size: int = 50
) -> Tuple[List[Scope], int]:
    """Retrieve all active scopes in the system with pagination (Admin view)."""
    offset = (page - 1) * page_size
    query = (
        select(Scope)
        .where(Scope.deleted_at.is_(None))
        .order_by(Scope.created_at.desc())
    )
    count_query = select(func.count(Scope.id)).where(Scope.deleted_at.is_(None))

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    result = await db.execute(query.offset(offset).limit(page_size))
    scopes = list(result.scalars().all())
    return scopes, total

async def create_scope(
    db: AsyncSession, scope_in: ScopeCreate, owner_id: uuid.UUID, actor_id: uuid.UUID
) -> Scope:
    """Create a new scope and log the audit entry."""
    db_scope = Scope(
        owner_id=owner_id,
        name=scope_in.name,
        type=scope_in.type,
        definition=scope_in.definition,
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_scope)
    await db.commit()
    await db.refresh(db_scope)

    await create_audit_entry(
        db=db,
        actor_id=actor_id,
        action="create_scope",
        target_type="scope",
        target_id=db_scope.id,
        metadata={"name": db_scope.name, "type": db_scope.type}
    )
    return db_scope

async def update_scope(
    db: AsyncSession, scope_id: uuid.UUID, scope_in: ScopeUpdate, actor_id: uuid.UUID
) -> Optional[Scope]:
    """Update an existing scope and log the audit entry."""
    db_scope = await get_scope_by_id(db, scope_id)
    if not db_scope:
        return None

    update_data = scope_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_scope, field, value)

    await db.commit()
    await db.refresh(db_scope)

    await create_audit_entry(
        db=db,
        actor_id=actor_id,
        action="update_scope",
        target_type="scope",
        target_id=db_scope.id,
        metadata={"fields_updated": list(update_data.keys())}
    )
    return db_scope

async def delete_scope(
    db: AsyncSession, scope_id: uuid.UUID, actor_id: uuid.UUID
) -> bool:
    """Soft-delete a scope and log the audit entry."""
    db_scope = await get_scope_by_id(db, scope_id)
    if not db_scope:
        return False

    db_scope.deleted_at = datetime.now(timezone.utc)
    db_scope.deleted_by = actor_id
    await db.commit()

    await create_audit_entry(
        db=db,
        actor_id=actor_id,
        action="delete_scope",
        target_type="scope",
        target_id=scope_id,
        metadata={"name": db_scope.name}
    )
    return True
