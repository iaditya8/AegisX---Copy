import uuid
from datetime import datetime, timezone
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession


class GraphSnapshotService:
    # in-memory snapshot cache: scope_id -> snapshot dict
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear the snapshot cache."""
        cls._snapshots.clear()

    @classmethod
    async def generate_snapshot(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None
    ) -> dict:
        """Generate and cache a summary snapshot from source nodes and edges."""
        from src.services.security_intelligence_graph_service import SecurityIntelligenceGraphService
        from src.domain.entities.security_intelligence_graph import GraphComponentStatus

        nodes = SecurityIntelligenceGraphService.get_all_nodes()
        edges = SecurityIntelligenceGraphService.get_all_edges()

        if scope_id:
            nodes = [n for n in nodes if n.scope_id == scope_id]
            edges = [e for e in edges if e.scope_id == scope_id]

        active_nodes = [n for n in nodes if n.status != GraphComponentStatus.DEPRECATED]
        active_edges = [e for e in edges if e.status != GraphComponentStatus.DEPRECATED]

        total_nodes = len(active_nodes)
        total_edges = len(active_edges)

        avg_weight = 0.0
        if total_edges > 0:
            avg_weight = sum(e.weight for e in active_edges) / total_edges

        density = 0.0
        if total_nodes > 1:
            density = (2.0 * total_edges) / (total_nodes * (total_nodes - 1))

        snapshot = {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "density": density,
            "average_weight": avg_weight,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        cls._snapshots[scope_id] = snapshot
        return snapshot

    @classmethod
    async def get_snapshot(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None
    ) -> dict:
        """Retrieve snapshot, auto-rebuilding it if missing or corrupted."""
        snap = cls._snapshots.get(scope_id)
        if not snap or not isinstance(snap, dict) or "total_nodes" not in snap:
            snap = await cls.generate_snapshot(db, scope_id)
        return snap
