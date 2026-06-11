import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.security import generate_api_key, hash_api_key, hash_password
from src.domain.entities.user import UserCreate, UserUpdate
from src.infrastructure.database.models import User


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """Retrieve an active user by ID."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Retrieve an active user by username."""
    result = await db.execute(
        select(User).where(User.username == username, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_users(
    db: AsyncSession, page: int = 1, page_size: int = 50
) -> Tuple[List[User], int]:
    """List active users with offset pagination and return total count."""
    offset = (page - 1) * page_size
    query = (
        select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
    )

    # Count total users
    count_query = select(func.count(User.id)).where(User.deleted_at.is_(None))
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Query paginated page
    result = await db.execute(query.offset(offset).limit(page_size))
    users = list(result.scalars().all())
    return users, total


async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    """Create a new user with unique username/email verification."""
    # Validate unique username
    existing_username = await get_user_by_username(db, user_in.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already registered"
        )

    # Validate unique email if provided
    if user_in.email:
        email_result = await db.execute(
            select(User).where(User.email == user_in.email, User.deleted_at.is_(None))
        )
        if email_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
            )

    db_user = User(
        username=user_in.username,
        display_name=user_in.display_name,
        email=user_in.email,
        role=user_in.role,
        password_hash=hash_password(user_in.password),
        created_at=datetime.now(timezone.utc),
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def update_user(
    db: AsyncSession, user_id: uuid.UUID, user_in: UserUpdate
) -> Optional[User]:
    """Update user fields, including password re-hashing if modified."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data:
        user.password_hash = hash_password(update_data["password"])
        del update_data["password"]

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(
    db: AsyncSession, user_id: uuid.UUID, deleted_by: Optional[uuid.UUID] = None
) -> bool:
    """Soft-delete a user by recording deleted timestamp and actor."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return False

    user.deleted_at = datetime.now(timezone.utc)
    user.deleted_by = deleted_by
    await db.commit()
    return True


async def generate_api_key_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> Optional[str]:
    """Generate and return a new API key, storing its hash in the database."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    raw_key = generate_api_key()
    user.api_key_hash = hash_api_key(raw_key)
    await db.commit()
    return raw_key
