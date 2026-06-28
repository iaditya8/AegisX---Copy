import uuid
from typing import Dict, Optional
from src.services.autonomous_security_planning_service import AutonomousSecurityPlanningService


class PlanningSnapshotService:
    # in-memory snapshot cache: scope_id -> snapshot dict
    _snapshots: Dict[uuid.UUID, dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear all cached snapshots."""
        cls._snapshots.clear()

    @classmethod
    async def generate_snapshot(cls, db, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Generate and cache a planning snapshot for a specific scope (or global if None)."""
        plans = AutonomousSecurityPlanningService.get_all_plans()
        if scope_id:
            plans = [p for p in plans if p.scope_id == scope_id]

        total = len(plans)
        app_count = sum(1 for p in plans if p.status.value == "APPROVED")
        act_count = sum(1 for p in plans if p.status.value == "ACTIVE")
        clo_count = sum(1 for p in plans if p.status.value == "CLOSED")

        progress_sum = 0.0
        plans_with_milestones = 0
        for p in plans:
            if p.milestones:
                completed = sum(1 for m in p.milestones if m.status == "COMPLETED")
                progress_sum += completed / len(p.milestones)
                plans_with_milestones += 1

        avg_progress = progress_sum / plans_with_milestones if plans_with_milestones > 0 else 0.0

        snap = {
            "total_plans": total,
            "approved_count": app_count,
            "active_count": act_count,
            "closed_count": clo_count,
            "average_progress": avg_progress,
        }

        # Store in cache
        cls._snapshots[scope_id] = snap
        return snap

    @classmethod
    async def get_snapshot(cls, db, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Get cached snapshot or rebuild dynamically from active source data if missing/corrupted."""
        snap = cls._snapshots.get(scope_id)

        # Rebuild if missing, deleted, or corrupted (missing keys)
        required_keys = {
            "total_plans",
            "approved_count",
            "active_count",
            "closed_count",
            "average_progress",
        }
        if not snap or not isinstance(snap, dict) or not required_keys.issubset(snap.keys()):
            snap = await cls.generate_snapshot(db, scope_id)

        return snap
