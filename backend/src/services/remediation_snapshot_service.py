import uuid
from typing import Dict


class RemediationSnapshotService:
    # in-memory store: asset_id -> snapshot dict
    _snapshots: Dict[uuid.UUID, Dict[str, int]] = {}

    @classmethod
    def get_snapshot(cls, asset_id: uuid.UUID) -> Dict[str, int]:
        """Get the cached snapshot for an asset. If not found, rebuild it."""
        if asset_id not in cls._snapshots:
            cls.update_snapshot(asset_id)
        return cls._snapshots.get(
            asset_id,
            {
                "open": 0,
                "in_progress": 0,
                "remediated": 0,
                "accepted_risk": 0,
                "false_positive": 0,
                "deferred": 0,
                "overdue": 0,
                "sla_breached": 0,
            },
        )

    @classmethod
    def update_snapshot(cls, asset_id: uuid.UUID) -> Dict[str, int]:
        """Rebuild and cache the remediation snapshot for an asset."""
        from src.services.remediation_aging_service import RemediationAgingService
        from src.services.remediation_service import RemediationService

        remediations = RemediationService.get_remediations_by_asset(asset_id)

        counts = {
            "open": 0,
            "in_progress": 0,
            "remediated": 0,
            "accepted_risk": 0,
            "false_positive": 0,
            "deferred": 0,
            "overdue": 0,
            "sla_breached": 0,
        }

        for r in remediations:
            status = r.status.value.lower()
            if status in counts:
                counts[status] += 1

            is_breached = RemediationAgingService.is_breached(r)
            if is_breached:
                counts["sla_breached"] += 1
                if status not in ["remediated", "accepted_risk", "false_positive"]:
                    counts["overdue"] += 1

        cls._snapshots[asset_id] = counts
        return counts

    @classmethod
    def generate_snapshot(cls, asset_id: uuid.UUID) -> Dict[str, int]:
        """Generate and cache snapshot directly."""
        return cls.update_snapshot(asset_id)

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear all cached snapshots."""
        cls._snapshots.clear()
