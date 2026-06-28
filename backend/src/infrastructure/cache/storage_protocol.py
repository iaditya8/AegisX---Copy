from typing import Any, List, Optional, Protocol


class CacheStorageProtocol(Protocol):
    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache by key."""
        ...

    def set(self, key: str, value: Any) -> None:
        """Store a value in the cache by key."""
        ...

    def delete(self, key: str) -> None:
        """Remove a key and its value from the cache."""
        ...

    def keys(self, pattern: str) -> List[str]:
        """Retrieve all keys matching a specific pattern."""
        ...

    def clear(self) -> None:
        """Clear all entries in this cache namespace."""
        ...

    def acquire_lock(self, lock_key: str, ttl_seconds: int = 10) -> bool:
        """Acquire a lock for concurrency control. Returns True if successful."""
        ...

    def release_lock(self, lock_key: str) -> None:
        """Release a previously acquired lock."""
        ...
