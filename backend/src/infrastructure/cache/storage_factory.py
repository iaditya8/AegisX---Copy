from src.core.config import settings
from src.infrastructure.cache.memory_storage_adapter import MemoryStorageAdapter
from src.infrastructure.cache.redis_storage_adapter import RedisStorageAdapter
from src.infrastructure.cache.storage_protocol import CacheStorageProtocol


class StorageFactory:
    @classmethod
    def get_adapter(cls, namespace: str) -> CacheStorageProtocol:
        """Resolve the configured cache storage provider dynamically."""
        if settings.ENVIRONMENT == "testing":
            return MemoryStorageAdapter(namespace)

        provider = getattr(settings, "CACHE_PROVIDER", "memory")
        if provider == "redis":
            return RedisStorageAdapter(namespace)

        return MemoryStorageAdapter(namespace)
