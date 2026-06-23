import time
from typing import Any, Dict, Optional, Tuple


class AICacheService:
    # In-memory store: Tuple[id, version, prompt_hash] -> Dict[str, Any]
    # Value format: {"payload": Dict[str, Any], "timestamp": float, "asset_id": str}
    _cache: Dict[Tuple[Any, str, str], Dict[str, Any]] = {}

    @classmethod
    def get(cls, key: Tuple[Any, str, str]) -> Optional[Dict[str, Any]]:
        """Retrieve a cached payload if it exists and is under 1 hour old."""
        entry = cls._cache.get(key)
        if not entry:
            return None

        # 1 hour TTL = 3600 seconds
        if time.time() - entry["timestamp"] > 3600.0:
            cls._cache.pop(key, None)
            return None

        return entry["payload"]

    @classmethod
    def set(
        cls, key: Tuple[Any, str, str], payload: Dict[str, Any], asset_id: Any
    ) -> None:
        """Store a payload in the cache associated with an asset ID."""
        cls._cache[key] = {
            "payload": payload,
            "timestamp": time.time(),
            "asset_id": str(asset_id) if asset_id else None,
        }

    @classmethod
    def invalidate_for_asset(cls, asset_id: Any) -> None:
        """Invalidate all cached entries associated with the asset."""
        asset_id_str = str(asset_id)
        keys_to_remove = [
            k
            for k, v in cls._cache.items()
            if v.get("asset_id") == asset_id_str or str(k[0]) == asset_id_str
        ]
        for k in keys_to_remove:
            cls._cache.pop(k, None)

    @classmethod
    def invalidate_all(cls) -> None:
        """Clear all cached AI responses."""
        cls._cache.clear()
