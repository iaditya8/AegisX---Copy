import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession


from src.infrastructure.cache.cache_dict import CacheList


class GraphDriftService:
    # In-memory drift log
    _drifts = CacheList("graph_drifts")

    @classmethod
    def clear_drifts(cls) -> None:
        """Clear all in-memory graph drift logs."""
        cls._drifts.clear()

    @classmethod
    def get_drifts(cls) -> List[dict]:
        """Retrieve all graph drift events."""
        return cls._drifts

    @classmethod
    async def process_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Analyze graph topology changes and emit drift events."""
        from src.services.security_intelligence_graph_service import SecurityIntelligenceGraphService
        from src.services.workflow_event_service import WorkflowEventService

        nodes = SecurityIntelligenceGraphService.get_all_nodes()
        edges = SecurityIntelligenceGraphService.get_all_edges()

        if scope_id:
            nodes = [n for n in nodes if n.scope_id == scope_id]
            edges = [e for e in edges if e.scope_id == scope_id]

        total_nodes = len(nodes)
        total_edges = len(edges)
        sum_weights = sum(e.weight for e in edges)

        if not prev_snapshot:
            return

        prev_nodes = prev_snapshot.get("total_nodes", 0)
        prev_edges = prev_snapshot.get("total_edges", 0)
        prev_weight = prev_snapshot.get("average_weight", 0.0) * prev_edges if prev_edges else 0.0

        drifted = False
        details = []

        if total_nodes != prev_nodes:
            drifted = True
            details.append(f"Node count shifted from {prev_nodes} to {total_nodes}")

        if total_edges != prev_edges:
            drifted = True
            details.append(f"Edge count shifted from {prev_edges} to {total_edges}")

        if abs(sum_weights - prev_weight) > 0.01:
            drifted = True
            details.append(f"Total edge weight shifted from {prev_weight} to {sum_weights}")

        if drifted:
            drift_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "scope_id": str(scope_id) if scope_id else None,
                "details": "; ".join(details),
            }
            cls._drifts.append(drift_entry)

            await WorkflowEventService.emit_event(
                db=db,
                event_type="graph.drift",
                payload=drift_entry,
            )
            await WorkflowEventService.emit_event(
                db=db,
                event_type="graph.structure_changed",
                payload=drift_entry,
            )
Definition: "Process structural and weight changes in security graph topology."
