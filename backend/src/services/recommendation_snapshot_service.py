import uuid
from typing import Any, Dict


class RecommendationSnapshotService:
    # in-memory store: asset_id -> snapshot dict
    _snapshots: Dict[uuid.UUID, Dict[str, Any]] = {}

    @classmethod
    async def generate_snapshot(cls, db: Any, asset_id: uuid.UUID) -> Dict[str, Any]:
        """Generate recommendation snapshot by calculating totals and priorities."""
        from src.services.recommendation_service import RecommendationService

        recs = await RecommendationService.generate_asset_recommendations(db, asset_id)

        by_priority = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        by_type: Dict[str, int] = {}

        for r in recs:
            pri = r.priority.value if hasattr(r.priority, "value") else str(r.priority)
            typ = r.type.value if hasattr(r.type, "value") else str(r.type)

            by_priority[pri] = by_priority.get(pri.upper(), 0) + 1
            by_type[typ] = by_type.get(typ.upper(), 0) + 1

        snapshot = {
            "asset_id": str(asset_id),
            "total_recommendations": len(recs),
            "by_priority": by_priority,
            "by_type": by_type,
        }
        return snapshot

    @classmethod
    async def update_snapshot(cls, db: Any, asset_id: uuid.UUID) -> Dict[str, Any]:
        """Recompute and cache recommendation snapshot for the asset."""
        snapshot = await cls.generate_snapshot(db, asset_id)
        cls._snapshots[asset_id] = snapshot
        return snapshot

    @classmethod
    def get_snapshot(cls, asset_id: uuid.UUID) -> Dict[str, Any]:
        """Retrieve cached recommendation snapshot."""
        return cls._snapshots.get(
            asset_id,
            {
                "asset_id": str(asset_id),
                "total_recommendations": 0,
                "by_priority": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
                "by_type": {},
            },
        )

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear the in-memory snapshots cache."""
        cls._snapshots.clear()
