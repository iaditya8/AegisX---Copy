import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from src.services.hunt_service import HuntService
from src.services.hunt_coverage_service import HuntCoverageService


class HuntSnapshotService:
    # Cache-only store: scope_id (Optional[uuid.UUID]) -> snapshot dict
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear all cached snapshots."""
        cls._snapshots.clear()

    @classmethod
    def generate_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Generate a new snapshot dynamically from active hunt records (cache consistency)."""
        hunts = HuntService.get_all_hunts()
        if scope_id:
            hunts = [h for h in hunts if h.scope_id == scope_id]

        total_hunts = len(hunts)
        open_hunts = len([h for h in hunts if h.status.value == "OPEN"])
        active_hunts = len([h for h in hunts if h.status.value == "ACTIVE"])
        completed_hunts = len([h for h in hunts if h.status.value == "COMPLETED"])

        # Fetch coverage metrics
        coverage_metrics = HuntCoverageService.calculate_coverage(scope_id)

        snapshot = {
            "summary": {
                "total_hunts": total_hunts,
                "open_hunts": open_hunts,
                "active_hunts": active_hunts,
                "completed_hunts": completed_hunts,
            },
            "coverage": coverage_metrics,
            "hunts": {
                str(h.hunt_id): {
                    "title": h.title,
                    "description": h.description,
                    "hunt_type": h.hunt_type.value,
                    "severity": h.severity.value,
                    "status": h.status.value,
                    "owner_id": str(h.owner_id) if h.owner_id else None,
                    "related_entities": h.related_entities,
                }
                for h in hunts
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        cls._snapshots[scope_id] = snapshot
        return snapshot

    @classmethod
    def get_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Get the cached snapshot, rebuilding dynamically if missing (consistency)."""
        if scope_id not in cls._snapshots or cls._snapshots[scope_id] is None:
            return cls.generate_snapshot(scope_id)
        return cls._snapshots[scope_id]
