import uuid
from typing import Dict, Optional
from src.services.security_decision_service import SecurityDecisionService


class DecisionSnapshotService:
    # in-memory snapshot cache: scope_id -> snapshot dict
    _snapshots: Dict[uuid.UUID, dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear all cached snapshots."""
        cls._snapshots.clear()

    @classmethod
    async def generate_snapshot(cls, db, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Generate and cache a decision snapshot for a specific scope (or global if None)."""
        decisions = SecurityDecisionService.get_all_decisions()
        if scope_id:
            decisions = [d for d in decisions if d.scope_id == scope_id]

        total = len(decisions)
        rec_count = sum(1 for d in decisions if d.status.value == "RECOMMENDED")
        com_count = sum(1 for d in decisions if d.status.value == "COMMITTED")
        arch_count = sum(1 for d in decisions if d.status.value == "ARCHIVED")

        total_benefit = 0.0
        benefit_count = 0
        for d in decisions:
            if d.tradeoff_matrix and d.tradeoff_matrix.net_benefit is not None:
                total_benefit += d.tradeoff_matrix.net_benefit
                benefit_count += 1

        avg_benefit = total_benefit / benefit_count if benefit_count > 0 else 0.0

        snap = {
            "total_decisions": total,
            "recommended_count": rec_count,
            "committed_count": com_count,
            "archived_count": arch_count,
            "average_net_benefit": avg_benefit,
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
            "total_decisions",
            "recommended_count",
            "committed_count",
            "archived_count",
            "average_net_benefit",
        }
        if not snap or not isinstance(snap, dict) or not required_keys.issubset(snap.keys()):
            snap = await cls.generate_snapshot(db, scope_id)

        return snap
