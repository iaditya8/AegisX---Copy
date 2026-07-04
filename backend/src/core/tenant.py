from contextvars import ContextVar
import uuid
from typing import Optional

_current_tenant_id: ContextVar[Optional[uuid.UUID]] = ContextVar("current_tenant_id", default=None)


def get_current_tenant_id() -> Optional[uuid.UUID]:
    return _current_tenant_id.get()


def set_current_tenant_id(tenant_id: Optional[uuid.UUID]) -> None:
    _current_tenant_id.set(tenant_id)
