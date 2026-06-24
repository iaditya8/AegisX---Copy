from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession


class MonitoringSnapshotService:
    _snapshot: Optional[Dict[str, int]] = None

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear the cached platform monitoring snapshot."""
        cls._snapshot = None

    @classmethod
    async def get_snapshot(cls, db: AsyncSession) -> Dict[str, int]:
        """Retrieve cumulative metrics snapshot, rebuilding if empty."""
        if cls._snapshot is None:
            await cls.update_snapshot(db)
        return cls._snapshot or {
            "added_assets": 0,
            "removed_assets": 0,
            "modified_assets": 0,
            "added_findings": 0,
            "resolved_findings": 0,
            "rediscovered_findings": 0,
            "risk_increases": 0,
            "risk_decreases": 0,
            "governance_changes": 0,
        }

    @classmethod
    async def update_snapshot(cls, db: AsyncSession) -> Dict[str, int]:
        """Aggregate snapshot metrics by traversing event logs."""
        from src.services.continuous_refresh_service import (
            ContinuousRefreshService,
        )

        events = ContinuousRefreshService.get_all_events()

        snapshot = {
            "added_assets": 0,
            "removed_assets": 0,
            "modified_assets": 0,
            "added_findings": 0,
            "resolved_findings": 0,
            "rediscovered_findings": 0,
            "risk_increases": 0,
            "risk_decreases": 0,
            "governance_changes": 0,
        }

        for event in events:
            if event.change_type == "ASSET_ADDED":
                snapshot["added_assets"] += 1
            elif event.change_type == "ASSET_REMOVED":
                snapshot["removed_assets"] += 1
            elif event.change_type == "ASSET_MODIFIED":
                snapshot["modified_assets"] += 1
            elif event.change_type == "FINDING_ADDED":
                snapshot["added_findings"] += 1
            elif event.change_type == "FINDING_RESOLVED":
                snapshot["resolved_findings"] += 1
            elif event.change_type == "FINDING_REDISCOVERED":
                snapshot["rediscovered_findings"] += 1
            elif event.change_type == "RISK_INCREASED":
                snapshot["risk_increases"] += 1
            elif event.change_type == "RISK_DECREASED":
                snapshot["risk_decreases"] += 1
            elif event.change_type in [
                "COMPLIANCE_FAILED",
                "COMPLIANCE_RESTORED",
                "RISK_ACCEPTANCE_EXPIRED",
                "GOVERNANCE_DRIFT",
            ]:
                snapshot["governance_changes"] += 1

        cls._snapshot = snapshot
        return cls._snapshot
