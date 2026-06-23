import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.plugin import PluginCreate
from src.infrastructure.database.models import Plugin, PluginEvent
from src.plugins.host import PluginHost, PluginValidationError


async def get_plugin_by_id(db: AsyncSession, plugin_id: uuid.UUID) -> Optional[Plugin]:
    """Retrieve active (not soft-deleted) plugin by ID."""
    query = select(Plugin).where(Plugin.id == plugin_id, Plugin.deleted_at.is_(None))
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_plugin_by_name(db: AsyncSession, name: str) -> Optional[Plugin]:
    """Retrieve active plugin by name."""
    query = select(Plugin).where(Plugin.name == name, Plugin.deleted_at.is_(None))
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def list_plugins(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[Plugin], int]:
    """List plugins with pagination."""
    offset = (page - 1) * page_size
    query = (
        select(Plugin)
        .where(Plugin.deleted_at.is_(None))
        .order_by(Plugin.installed_at.desc())
    )
    count_query = select(func.count(Plugin.id)).where(Plugin.deleted_at.is_(None))

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    result = await db.execute(query.offset(offset).limit(page_size))
    plugins = list(result.scalars().all())
    return plugins, total


async def register_plugin(db: AsyncSession, plugin_in: PluginCreate) -> Plugin:
    """Register a new plugin definition. Starts in 'draft' state."""
    # Check if a plugin with the same name already exists
    existing = await get_plugin_by_name(db, plugin_in.name)
    if existing:
        raise ValueError(f"Plugin with name '{plugin_in.name}' already registered")

    db_plugin = Plugin(
        name=plugin_in.name,
        version=plugin_in.version,
        manifest=plugin_in.manifest.model_dump(),
        state="draft",  # Newly registered plugins start in draft state
        installed_at=datetime.now(timezone.utc),
    )
    db.add(db_plugin)
    await db.commit()
    await db.refresh(db_plugin)

    # Log plugin.loaded event
    await PluginHost.log_event(
        db, db_plugin.id, "plugin.loaded", payload={"manifest": db_plugin.manifest}
    )

    return db_plugin


async def validate_plugin_by_id(db: AsyncSession, plugin_id: uuid.UUID) -> bool:
    """Run validation engine checks on the plugin manifest and implementation."""
    plugin = await get_plugin_by_id(db, plugin_id)
    if not plugin:
        raise ValueError("Plugin not found")

    try:
        # Validate entry_point and manifest definition via PluginHost
        PluginHost.validate_plugin(plugin.manifest.get("entry_point"), plugin.manifest)

        # Log plugin.validated event
        await PluginHost.log_event(
            db, plugin.id, "plugin.validated", payload={"status": "success"}
        )
        return True
    except PluginValidationError as e:
        # Log plugin.failed event on validation failure
        await PluginHost.log_event(
            db,
            plugin.id,
            "plugin.failed",
            payload={"error": str(e), "stage": "validation"},
        )
        raise e


async def approve_plugin_by_id(db: AsyncSession, plugin_id: uuid.UUID) -> Plugin:
    """Transition state to 'approved'. Requires successful validation."""
    plugin = await get_plugin_by_id(db, plugin_id)
    if not plugin:
        raise ValueError("Plugin not found")

    # Run validation (will raise PluginValidationError if fails)
    await validate_plugin_by_id(db, plugin_id)

    # Transition state
    plugin.state = "approved"
    await db.commit()
    await db.refresh(plugin)
    return plugin


async def disable_plugin_by_id(db: AsyncSession, plugin_id: uuid.UUID) -> Plugin:
    """Transition state to 'disabled'."""
    plugin = await get_plugin_by_id(db, plugin_id)
    if not plugin:
        raise ValueError("Plugin not found")

    plugin.state = "disabled"
    await db.commit()
    await db.refresh(plugin)

    # Log plugin.disabled
    await PluginHost.log_event(db, plugin.id, "plugin.disabled")
    return plugin


async def deprecate_plugin_by_id(db: AsyncSession, plugin_id: uuid.UUID) -> Plugin:
    """Transition state to 'deprecated'."""
    plugin = await get_plugin_by_id(db, plugin_id)
    if not plugin:
        raise ValueError("Plugin not found")

    plugin.state = "deprecated"
    await db.commit()
    await db.refresh(plugin)

    # Log plugin.deprecated
    await PluginHost.log_event(db, plugin.id, "plugin.deprecated")
    return plugin


async def delete_plugin(
    db: AsyncSession, plugin_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Soft delete a plugin definition."""
    plugin = await get_plugin_by_id(db, plugin_id)
    if not plugin:
        return False

    plugin.deleted_at = datetime.now(timezone.utc)
    plugin.deleted_by = user_id
    await db.commit()
    return True


async def list_plugin_events(
    db: AsyncSession,
    plugin_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[PluginEvent], int]:
    """Retrieve paginated events for a plugin."""
    offset = (page - 1) * page_size
    query = (
        select(PluginEvent)
        .where(PluginEvent.plugin_id == plugin_id)
        .order_by(PluginEvent.timestamp.desc())
    )
    count_query = select(func.count(PluginEvent.id)).where(
        PluginEvent.plugin_id == plugin_id
    )

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    result = await db.execute(query.offset(offset).limit(page_size))
    events = list(result.scalars().all())
    return events, total
