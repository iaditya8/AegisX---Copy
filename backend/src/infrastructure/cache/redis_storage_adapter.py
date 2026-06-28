import pickle
import redis
from typing import Any, List, Optional


class RedisStorageAdapter:
    def __init__(self, namespace: str):
        from src.core.config import settings
        self.namespace = namespace
        self._client = redis.from_url(settings.REDIS_URL)

    def _get_key(self, key: str) -> str:
        return f"aegisx:{self.namespace}:{key}"

    def get(self, key: str) -> Optional[Any]:
        try:
            data = self._client.get(self._get_key(key))
            if data is not None:
                return pickle.loads(data)
            return None
        except Exception:
            return None

    def set(self, key: str, value: Any) -> None:
        try:
            data = pickle.dumps(value)
            self._client.set(self._get_key(key), data)
        except Exception:
            pass

    def delete(self, key: str) -> None:
        try:
            self._client.delete(self._get_key(key))
        except Exception:
            pass

    def keys(self, pattern: str) -> List[str]:
        try:
            full_pattern = f"aegisx:{self.namespace}:{pattern}"
            matched = self._client.keys(full_pattern)
            prefix = f"aegisx:{self.namespace}:"
            prefix_len = len(prefix)
            return [m.decode("utf-8")[prefix_len:] for m in matched]
        except Exception:
            return []

    def clear(self) -> None:
        try:
            full_pattern = f"aegisx:{self.namespace}:*"
            keys = self._client.keys(full_pattern)
            if keys:
                self._client.delete(*keys)
        except Exception:
            pass

    def acquire_lock(self, lock_key: str, ttl_seconds: int = 10) -> bool:
        try:
            full_lock_key = f"aegisx:{self.namespace}:lock:{lock_key}"
            ms_ttl = ttl_seconds * 1000
            acquired = self._client.set(full_lock_key, b"locked", nx=True, px=ms_ttl)
            return bool(acquired)
        except Exception:
            return True

    def release_lock(self, lock_key: str) -> None:
        try:
            full_lock_key = f"aegisx:{self.namespace}:lock:{lock_key}"
            self._client.delete(full_lock_key)
        except Exception:
            pass
