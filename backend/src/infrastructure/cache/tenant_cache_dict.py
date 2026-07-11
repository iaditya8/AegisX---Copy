import uuid
from typing import Any, List, Optional, Tuple
from src.core.tenant import require_current_tenant_id


class TenantCacheDict:
    """Thread-safe, tenant-partitioned L2 cache.
    
    Keys are automatically prefixed with the current tenant_id.
    """

    def __init__(self, namespace: str):
        self.namespace = namespace
        self._adapter = None

    @property
    def adapter(self):
        if self._adapter is None:
            from src.infrastructure.cache.storage_factory import StorageFactory
            self._adapter = StorageFactory.get_adapter(self.namespace)
        return self._adapter

    def _tenant_key(self, key: Any, tenant_id: Optional[uuid.UUID] = None) -> str:
        tid = tenant_id or require_current_tenant_id()
        return f"{tid}:{key}"

    def clear(self) -> None:
        """Clear all keys in this namespace across all tenants (system operation)."""
        self.adapter.clear()

    def clear_tenant(self, tenant_id: Optional[uuid.UUID] = None) -> None:
        """Clear all keys for a specific tenant."""
        tid = tenant_id or require_current_tenant_id()
        prefix = f"{tid}:"
        for k in self.adapter.keys(f"{prefix}*"):
            self.adapter.delete(k)

    def values(self) -> List[Any]:
        tid = require_current_tenant_id()
        prefix = f"{tid}:"
        keys = self.adapter.keys(f"{prefix}*")
        results = []
        for k in keys:
            val = self.adapter.get(k)
            if val is not None:
                results.append(val)
        return results

    def get(self, key: Any, default: Optional[Any] = None) -> Any:
        tid = require_current_tenant_id()
        val = self.adapter.get(self._tenant_key(key, tid))
        return val if val is not None else default

    def get_for_tenant(self, tenant_id: uuid.UUID, key: Any, default: Optional[Any] = None) -> Any:
        val = self.adapter.get(self._tenant_key(key, tenant_id))
        return val if val is not None else default

    def set_for_tenant(self, tenant_id: uuid.UUID, key: Any, value: Any) -> None:
        self.adapter.set(self._tenant_key(key, tenant_id), value)

    def __getitem__(self, key: Any) -> Any:
        tid = require_current_tenant_id()
        val = self.adapter.get(self._tenant_key(key, tid))
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key: Any, value: Any) -> None:
        tid = require_current_tenant_id()
        self.adapter.set(self._tenant_key(key, tid), value)

    def __delitem__(self, key: Any) -> None:
        tid = require_current_tenant_id()
        self.adapter.delete(self._tenant_key(key, tid))

    def __contains__(self, key: Any) -> bool:
        tid = require_current_tenant_id()
        return self.adapter.get(self._tenant_key(key, tid)) is not None

    def pop(self, key: Any, default: Optional[Any] = None) -> Any:
        tid = require_current_tenant_id()
        tkey = self._tenant_key(key, tid)
        val = self.adapter.get(tkey)
        if val is not None:
            self.adapter.delete(tkey)
            return val
        return default

    def items(self) -> List[Tuple[Any, Any]]:
        tid = require_current_tenant_id()
        prefix = f"{tid}:"
        keys = self.adapter.keys(f"{prefix}*")
        results = []
        for k in keys:
            val = self.adapter.get(k)
            if val is not None:
                # Strip tenant prefix from key for consumer compatibility
                raw_key = k[len(prefix):]
                try:
                    key_val = uuid.UUID(raw_key)
                except ValueError:
                    key_val = raw_key
                results.append((key_val, val))
        return results

    def __len__(self) -> int:
        tid = require_current_tenant_id()
        prefix = f"{tid}:"
        return len(self.adapter.keys(f"{prefix}*"))
