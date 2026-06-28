import uuid
from typing import Any, List, Optional, Tuple


class CacheDict:
    def __init__(self, namespace: str):
        self.namespace = namespace
        self._adapter = None

    @property
    def adapter(self):
        if self._adapter is None:
            from src.infrastructure.cache.storage_factory import StorageFactory
            self._adapter = StorageFactory.get_adapter(self.namespace)
        return self._adapter

    def clear(self) -> None:
        self.adapter.clear()

    def values(self) -> List[Any]:
        keys = self.adapter.keys("*")
        results = []
        for k in keys:
            val = self.adapter.get(k)
            if val is not None:
                results.append(val)
        return results

    def get(self, key: Any, default: Optional[Any] = None) -> Any:
        val = self.adapter.get(str(key))
        return val if val is not None else default

    def __getitem__(self, key: Any) -> Any:
        val = self.adapter.get(str(key))
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key: Any, value: Any) -> None:
        self.adapter.set(str(key), value)

    def __delitem__(self, key: Any) -> None:
        self.adapter.delete(str(key))

    def __contains__(self, key: Any) -> bool:
        return self.adapter.get(str(key)) is not None

    def pop(self, key: Any, default: Optional[Any] = None) -> Any:
        val = self.adapter.get(str(key))
        if val is not None:
            self.adapter.delete(str(key))
            return val
        return default

    def items(self) -> List[Tuple[Any, Any]]:
        keys = self.adapter.keys("*")
        results = []
        for k in keys:
            val = self.adapter.get(k)
            if val is not None:
                try:
                    key_val = uuid.UUID(k)
                except ValueError:
                    key_val = k
                results.append((key_val, val))
        return results


class CacheList:
    def __init__(self, namespace: str):
        self.namespace = namespace
        self._adapter = None

    @property
    def adapter(self):
        if self._adapter is None:
            from src.infrastructure.cache.storage_factory import StorageFactory
            self._adapter = StorageFactory.get_adapter(self.namespace)
        return self._adapter

    def get_list(self) -> List[Any]:
        return self.adapter.get("list") or []

    def clear(self) -> None:
        self.adapter.delete("list")

    def append(self, value: Any) -> None:
        acquired = self.adapter.acquire_lock("list_lock", ttl_seconds=5)
        if acquired:
            try:
                lst = self.get_list()
                lst.append(value)
                self.adapter.set("list", lst)
            finally:
                self.adapter.release_lock("list_lock")
    def __iter__(self):
        return iter(self.get_list())

    def __len__(self) -> int:
        return len(self.get_list())

    def __getitem__(self, index: Any) -> Any:
        return self.get_list()[index]

    def __add__(self, other: List[Any]) -> List[Any]:
        return self.get_list() + other
