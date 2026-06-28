import time
import threading
from typing import Dict, List, Optional


class MemoryStorageAdapter:
    # Class-level dictionary to simulate a shared Redis instance for local threads
    _global_data: Dict[str, Dict[str, str]] = {}
    _global_locks: Dict[str, threading.Lock] = {}
    _active_distributed_locks: Dict[str, float] = {}
    _lock = threading.Lock()

    def __init__(self, namespace: str):
        self.namespace = namespace
        with self._lock:
            if namespace not in self._global_data:
                self._global_data[namespace] = {}
            if namespace not in self._global_locks:
                self._global_locks[namespace] = threading.Lock()

        self._data = self._global_data[namespace]
        self._ns_lock = self._global_locks[namespace]

    def get(self, key: str) -> Optional[str]:
        with self._ns_lock:
            return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        with self._ns_lock:
            self._data[key] = value

    def delete(self, key: str) -> None:
        with self._ns_lock:
            self._data.pop(key, None)

    def keys(self, pattern: str) -> List[str]:
        # Simple glob-like starts-with prefix match for keys pattern
        prefix = pattern.replace("*", "")
        with self._ns_lock:
            return [k for k in self._data.keys() if k.startswith(prefix)]

    def clear(self) -> None:
        with self._ns_lock:
            self._data.clear()

    def acquire_lock(self, lock_key: str, ttl_seconds: int = 10) -> bool:
        full_key = f"{self.namespace}:lock:{lock_key}"
        with self._lock:
            now = time.time()
            # If lock exists and has not expired, block acquisition
            if full_key in self._active_distributed_locks:
                if self._active_distributed_locks[full_key] > now:
                    return False
            # Acquire/Renew lock
            self._active_distributed_locks[full_key] = now + ttl_seconds
            return True

    def release_lock(self, lock_key: str) -> None:
        full_key = f"{self.namespace}:lock:{lock_key}"
        with self._lock:
            self._active_distributed_locks.pop(full_key, None)
