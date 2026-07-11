from contextvars import ContextVar
import uuid
from typing import Optional

_current_tenant_id: ContextVar[Optional[uuid.UUID]] = ContextVar("current_tenant_id", default=None)


class TenantContextError(RuntimeError):
    """Raised when tenant context is required but missing."""
    pass


class TenantMismatchError(RuntimeError):
    """Raised when entity tenant_id does not match the current context."""
    pass


def get_current_tenant_id() -> Optional[uuid.UUID]:
    return _current_tenant_id.get()


def set_current_tenant_id(tenant_id: Optional[uuid.UUID]) -> None:
    _current_tenant_id.set(tenant_id)


def require_current_tenant_id() -> uuid.UUID:
    """Retrieve the current tenant ID, raising TenantContextError if none is set."""
    tenant_id = _current_tenant_id.get()
    if tenant_id is None:
        raise TenantContextError("Tenant context is required but was not set.")
    return tenant_id

