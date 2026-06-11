import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.asset import AssetCreate, AssetUpdate
from src.infrastructure.database.models import (
    Asset,
    AssetHistory,
    AssetRelationship,
    Scope,
)
from src.services.audit_service import create_audit_entry


async def get_asset_by_id(db: AsyncSession, asset_id: uuid.UUID) -> Optional[Asset]:
    """Retrieve an active asset (not soft-deleted) by ID."""
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.deleted_at.is_(None))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        return None

    if asset.scope_id:
        scope_result = await db.execute(
            select(Scope).where(
                Scope.id == asset.scope_id, Scope.deleted_at.is_(None)
            )
        )
        scope = scope_result.scalar_one_or_none()
        if not scope:
            return None

    return asset

async def get_assets_by_scope(
    db: AsyncSession,
    scope_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    host: Optional[str] = None,
    ip: Optional[str] = None
) -> Tuple[List[Asset], int]:
    """Retrieve active assets in a scope with pagination and filters."""
    offset = (page - 1) * page_size
    query = select(Asset).where(
        Asset.scope_id == scope_id, Asset.deleted_at.is_(None)
    )
    count_query = select(func.count(Asset.id)).where(
        Asset.scope_id == scope_id, Asset.deleted_at.is_(None)
    )

    if host:
        # Check case-insensitive match or exact
        query = query.where(Asset.host.ilike(f"%{host}%"))
        count_query = count_query.where(Asset.host.ilike(f"%{host}%"))
    if ip:
        query = query.where(Asset.ip == ip)
        count_query = count_query.where(Asset.ip == ip)

    query = query.order_by(Asset.first_seen.desc())

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    result = await db.execute(query.offset(offset).limit(page_size))
    assets = list(result.scalars().all())
    return assets, total

async def get_asset_relationships(
    db: AsyncSession, asset_id: uuid.UUID
) -> List[AssetRelationship]:
    """Retrieve relationships where the asset is either source or target."""
    result = await db.execute(
        select(AssetRelationship).where(
            (AssetRelationship.source_asset_id == asset_id) |
            (AssetRelationship.target_asset_id == asset_id)
        )
    )
    return list(result.scalars().all())

async def get_asset_history(
    db: AsyncSession, asset_id: uuid.UUID
) -> List[AssetHistory]:
    """Retrieve the revision history of an asset."""
    result = await db.execute(
        select(AssetHistory)
        .where(AssetHistory.asset_id == asset_id)
        .order_by(AssetHistory.timestamp.desc())
    )
    return list(result.scalars().all())

async def create_asset(
    db: AsyncSession, asset_in: AssetCreate, scope_id: uuid.UUID, actor_id: uuid.UUID
) -> Asset:
    """Create a new asset, log the audit entry, and write asset history."""
    now = datetime.now(timezone.utc)
    db_asset = Asset(
        scope_id=scope_id,
        host=asset_in.host,
        ip=asset_in.ip,
        asset_type=asset_in.asset_type,
        metadata_json=asset_in.metadata_json or {},
        first_seen=now,
        last_seen=now,
        fingerprint=asset_in.fingerprint,
    )
    db.add(db_asset)
    await db.commit()
    await db.refresh(db_asset)

    # Record history
    db_history = AssetHistory(
        asset_id=db_asset.id,
        change_type="create",
        old_value=None,
        new_value={
            "host": db_asset.host,
            "ip": db_asset.ip,
            "asset_type": db_asset.asset_type,
            "metadata_json": db_asset.metadata_json,
            "fingerprint": db_asset.fingerprint,
        },
        timestamp=now
    )
    db.add(db_history)
    await db.commit()

    # Log audit entry
    await create_audit_entry(
        db=db,
        actor_id=actor_id,
        action="create_asset",
        target_type="asset",
        target_id=db_asset.id,
        metadata={
            "host": db_asset.host,
            "ip": db_asset.ip,
            "asset_type": db_asset.asset_type,
        }
    )
    return db_asset

async def update_asset(
    db: AsyncSession, asset_id: uuid.UUID, asset_in: AssetUpdate, actor_id: uuid.UUID
) -> Optional[Asset]:
    """Update an existing asset, log changes to history, and write audit log."""
    db_asset = await get_asset_by_id(db, asset_id)
    if not db_asset:
        return None

    update_data = asset_in.model_dump(exclude_unset=True)
    if not update_data:
        return db_asset

    old_values = {}
    new_values = {}

    for field, value in update_data.items():
        old_val = getattr(db_asset, field)
        if old_val != value:
            old_values[field] = old_val
            new_values[field] = value
            setattr(db_asset, field, value)

    if old_values or new_values:
        now = datetime.now(timezone.utc)
        db_asset.last_seen = now
        await db.commit()
        await db.refresh(db_asset)

        # Record history
        db_history = AssetHistory(
            asset_id=db_asset.id,
            change_type="update",
            old_value=old_values,
            new_value=new_values,
            timestamp=now
        )
        db.add(db_history)
        await db.commit()

        # Log audit entry
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="update_asset",
            target_type="asset",
            target_id=db_asset.id,
            metadata={"fields_updated": list(new_values.keys())}
        )
    return db_asset

async def delete_asset(
    db: AsyncSession, asset_id: uuid.UUID, actor_id: uuid.UUID
) -> bool:
    """Soft-delete an asset and log the audit entry."""
    db_asset = await get_asset_by_id(db, asset_id)
    if not db_asset:
        return False

    now = datetime.now(timezone.utc)
    db_asset.deleted_at = now
    db_asset.deleted_by = actor_id
    await db.commit()

    # Log audit entry
    await create_audit_entry(
        db=db,
        actor_id=actor_id,
        action="delete_asset",
        target_type="asset",
        target_id=asset_id,
        metadata={"host": db_asset.host, "ip": db_asset.ip}
    )
    return True

async def create_relationship(
    db: AsyncSession,
    source_asset_id: uuid.UUID,
    target_asset_id: uuid.UUID,
    relationship_type: str,
    metadata_json: Optional[Dict[str, Any]] = None,
    actor_id: Optional[uuid.UUID] = None
) -> AssetRelationship:
    """Create a relationship between two assets and log an audit entry."""
    db_rel = AssetRelationship(
        source_asset_id=source_asset_id,
        target_asset_id=target_asset_id,
        relationship_type=relationship_type,
        metadata_json=metadata_json or {},
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_rel)
    await db.commit()
    await db.refresh(db_rel)

    await create_audit_entry(
        db=db,
        actor_id=actor_id,
        action="create_relationship",
        target_type="asset_relationship",
        target_id=db_rel.id,
        metadata={
            "source_asset_id": str(source_asset_id),
            "target_asset_id": str(target_asset_id),
            "relationship_type": relationship_type
        }
    )
    return db_rel
