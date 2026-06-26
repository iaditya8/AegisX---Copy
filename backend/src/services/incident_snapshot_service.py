import uuid
from typing import Dict, Optional

from src.services.incident_service import IncidentService


class IncidentSnapshotService:
    # in-memory store: asset_id -> snapshot dict
    _snapshots: Dict[uuid.UUID, Dict[str, int]] = {}
    _global_snapshot: Optional[Dict[str, int]] = None

    @classmethod
    def _get_empty_counts(cls) -> Dict[str, int]:
        return {
            "open": 0,
            "triaged": 0,
            "investigating": 0,
            "escalated": 0,
            "contained": 0,
            "resolved": 0,
            "closed": 0,
            "total": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }

    @classmethod
    def get_snapshot(cls, asset_id: Optional[uuid.UUID] = None) -> Dict[str, int]:
        """Get the cached snapshot for an asset, or globally if None. Rebuilds dynamically if missing."""
        if asset_id is None:
            if cls._global_snapshot is None:
                cls.rebuild_global_snapshot()
            return cls._global_snapshot

        if asset_id not in cls._snapshots:
            cls.update_snapshot(asset_id)
        return cls._snapshots.get(asset_id, cls._get_empty_counts())

    @classmethod
    def update_snapshot(cls, asset_id: uuid.UUID) -> Dict[str, int]:
        """Rebuild and cache the incident snapshot for an asset."""
        incidents = IncidentService.get_all_incidents()
        asset_incidents = [inc for inc in incidents if asset_id in inc.asset_ids]

        counts = cls._get_empty_counts()
        for inc in asset_incidents:
            status = inc.status.value.lower()
            if status in counts:
                counts[status] += 1
            severity = inc.severity.value.lower()
            if severity in counts:
                counts[severity] += 1
            counts["total"] += 1

        cls._snapshots[asset_id] = counts
        return counts

    @classmethod
    def rebuild_global_snapshot(cls) -> Dict[str, int]:
        """Rebuild and cache the global incident snapshot."""
        incidents = IncidentService.get_all_incidents()

        counts = cls._get_empty_counts()
        for inc in incidents:
            status = inc.status.value.lower()
            if status in counts:
                counts[status] += 1
            severity = inc.severity.value.lower()
            if severity in counts:
                counts[severity] += 1
            counts["total"] += 1

        cls._global_snapshot = counts
        return counts

    @classmethod
    def generate_snapshot(cls, asset_id: uuid.UUID) -> Dict[str, int]:
        """Generate and cache snapshot directly."""
        return cls.update_snapshot(asset_id)

    @classmethod
    def invalidate_cache(cls) -> None:
        """Invalidate the cache by clearing snapshots."""
        cls.clear_snapshots()

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear all cached snapshots."""
        cls._snapshots.clear()
        cls._global_snapshot = None
