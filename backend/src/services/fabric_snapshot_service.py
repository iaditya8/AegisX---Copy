import uuid
from typing import Dict, Optional
from src.services.unified_security_intelligence_fabric_service import UnifiedSecurityIntelligenceFabricService


class FabricSnapshotService:
    # in-memory snapshot cache: scope_id -> snapshot dict
    _snapshots: Dict[uuid.UUID, dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear all cached snapshots."""
        cls._snapshots.clear()

    @classmethod
    async def generate_snapshot(cls, db, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Generate and cache a fabric snapshot for a specific scope (or global if None)."""
        nodes = UnifiedSecurityIntelligenceFabricService.get_all_fabric_nodes()
        if scope_id:
            nodes = [n for n in nodes if n.scope_id == scope_id]

        total = len(nodes)
        act_count = sum(1 for n in nodes if n.status.value == "ACTIVE")
        sus_count = sum(1 for n in nodes if n.status.value == "SUSPENDED")
        ter_count = sum(1 for n in nodes if n.status.value == "TERMINATED")

        conf_sum = 0.0
        conf_count = 0
        for n in nodes:
            if n.confidence_weights and "current_confidence" in n.confidence_weights:
                conf_sum += n.confidence_weights["current_confidence"]
                conf_count += 1

        avg_conf = conf_sum / conf_count if conf_count > 0 else 0.0

        snap = {
            "total_nodes": total,
            "active_count": act_count,
            "suspended_count": sus_count,
            "terminated_count": ter_count,
            "average_confidence": avg_conf,
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
            "total_nodes",
            "active_count",
            "suspended_count",
            "terminated_count",
            "average_confidence",
        }
        if not snap or not isinstance(snap, dict) or not required_keys.issubset(snap.keys()):
            snap = await cls.generate_snapshot(db, scope_id)

        return snap
