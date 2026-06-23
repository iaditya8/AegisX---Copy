import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.plugin import (
    PluginCreate,
    PluginEventResponse,
    PluginResponse,
)
from src.domain.entities.user import StandardResponse
from src.infrastructure.database.models import User
from src.infrastructure.database.session import get_db
from src.plugins.host import PluginValidationError
from src.services.plugin_service import (
    approve_plugin_by_id,
    deprecate_plugin_by_id,
    disable_plugin_by_id,
    list_plugin_events,
    list_plugins,
    register_plugin,
    validate_plugin_by_id,
)

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.get("", response_model=StandardResponse[List[PluginResponse]])
async def get_all_plugins(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[List[PluginResponse]]:
    """List all registered plugins with pagination. Admins only."""
    plugins, total = await list_plugins(db, page, page_size)
    return StandardResponse(
        data=[PluginResponse.model_validate(p) for p in plugins],
        meta={"total": total, "page": page, "page_size": page_size},
    )


@router.post(
    "",
    response_model=StandardResponse[PluginResponse],
    status_code=status.HTTP_201_CREATED,
)
async def register_new_plugin(
    plugin_in: PluginCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[PluginResponse]:
    """Register a new plugin.

    Newly registered plugins start in draft state. Admins only.
    """
    try:
        new_plugin = await register_plugin(db, plugin_in)
        response.headers["Location"] = f"/api/v1/plugins/{new_plugin.id}"
        return StandardResponse(data=PluginResponse.model_validate(new_plugin))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{id}/validate", response_model=StandardResponse[bool])
async def trigger_plugin_validation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[bool]:
    """Trigger the validation engine checks for the plugin. Admins only."""
    try:
        success = await validate_plugin_by_id(db, id)
        return StandardResponse(data=success)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PluginValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{id}/approve", response_model=StandardResponse[PluginResponse])
async def approve_plugin(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[PluginResponse]:
    """Approve a plugin.

    Validation is automatically run; fails if validation fails. Admins only.
    """
    try:
        plugin = await approve_plugin_by_id(db, id)
        return StandardResponse(data=PluginResponse.model_validate(plugin))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PluginValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{id}/disable", response_model=StandardResponse[PluginResponse])
async def disable_plugin(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[PluginResponse]:
    """Disable an active plugin. Disabled plugins cannot execute. Admins only."""
    try:
        plugin = await disable_plugin_by_id(db, id)
        return StandardResponse(data=PluginResponse.model_validate(plugin))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{id}/deprecate", response_model=StandardResponse[PluginResponse])
async def deprecate_plugin(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[PluginResponse]:
    """Deprecate a plugin.

    Deprecated plugins cannot be newly attached to workflows. Admins only.
    """
    try:
        plugin = await deprecate_plugin_by_id(db, id)
        return StandardResponse(data=PluginResponse.model_validate(plugin))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{id}/events", response_model=StandardResponse[List[PluginEventResponse]])
async def get_plugin_events(
    id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[List[PluginEventResponse]]:
    """Retrieve paginated events logged for the plugin. Admins only."""
    events, total = await list_plugin_events(db, id, page, page_size)
    return StandardResponse(
        data=[PluginEventResponse.model_validate(e) for e in events],
        meta={"total": total, "page": page, "page_size": page_size},
    )
