import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from src.services.detection_coverage_service import DetectionCoverageService


class DetectionSnapshotService:
    # Cache-only store: scope_id (Optional[uuid.UUID]) -> snapshot dict
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear all cached snapshots."""
        cls._snapshots.clear()

    @classmethod
    def generate_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Generate a new snapshot dynamically from active detection records and cache it."""
        coverage = DetectionCoverageService.calculate_coverage(scope_id)
        overall_score = DetectionCoverageService.calculate_overall_score(scope_id)

        snapshot = {
            "coverage_score": overall_score,
            "techniques": {
                c.technique_id: {
                    "coverage_status": c.coverage_status.value,
                    "detection_count": c.detection_count,
                }
                for c in coverage
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        cls._snapshots[scope_id] = snapshot
        return snapshot

    @classmethod
    def get_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Get the cached snapshot, rebuilding dynamically if missing (cache-only consistency)."""
        if scope_id not in cls._snapshots or cls._snapshots[scope_id] is None:
            return cls.generate_snapshot(scope_id)
        return cls._snapshots[scope_id]
