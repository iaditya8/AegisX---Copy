import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import WorkflowEvent
from src.services.correlation_service import CorrelationService


class CorrelationSnapshotService:
    """In-memory cache and service for asset correlation snapshots."""

    # In-memory store for snapshots
    _snapshots: Dict[uuid.UUID, Dict[str, Any]] = {}

    @classmethod
    async def generate_snapshot(
        cls, db: AsyncSession, asset_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Generate a correlation snapshot from CorrelationService."""
        correlation_data = await CorrelationService.correlate_asset(db, asset_id)

        # Ensure the output structure matches the required snapshot structure:
        # {
        #   "asset_id": "...",
        #   "exposure": "...",
        #   "ports": [],
        #   "services": [],
        #   "products": [],
        #   "finding_counts": {},
        #   "risk_factors": []
        # }
        snapshot = {
            "asset_id": str(asset_id),
            "exposure": correlation_data.get("exposure", "UNKNOWN"),
            "ports": correlation_data.get("ports", []),
            "services": correlation_data.get("services", []),
            "products": correlation_data.get("products", []),
            "finding_counts": correlation_data.get("finding_counts", {}),
            "risk_factors": correlation_data.get("risk_factors", []),
        }

        # Include technologies for compatibility/robustness
        snapshot["technologies"] = correlation_data.get("technologies", [])

        return snapshot

    @classmethod
    async def update_snapshot(
        cls,
        db: AsyncSession,
        asset_id: uuid.UUID,
        scan_run_id: Optional[uuid.UUID] = None,
        workflow_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Recompute and cache the snapshot. Emits a correlation.generated workflow event
        if workflow context is provided.
        """
        snapshot = await cls.generate_snapshot(db, asset_id)
        cls._snapshots[asset_id] = snapshot

        # Emit correlation.generated workflow event
        if workflow_id:
            event_id = uuid.uuid4()
            now = datetime.now(timezone.utc)
            event = WorkflowEvent(
                id=event_id,
                workflow_id=workflow_id,
                event_type="correlation.generated",
                correlation_id=scan_run_id,
                payload={
                    "event_id": str(event_id),
                    "correlation_id": str(scan_run_id) if scan_run_id else None,
                    "workflow_id": str(workflow_id),
                    "scan_run_id": str(scan_run_id) if scan_run_id else None,
                    "timestamp": now.isoformat(),
                    "asset_id": str(asset_id),
                },
                timestamp=now,
            )
            db.add(event)
            await db.commit()

        return snapshot

    @classmethod
    def get_snapshot(cls, asset_id: uuid.UUID) -> Dict[str, Any]:
        """Retrieve the cached correlation snapshot."""
        return cls._snapshots.get(
            asset_id,
            {
                "asset_id": str(asset_id),
                "exposure": "UNKNOWN",
                "ports": [],
                "services": [],
                "products": [],
                "finding_counts": {},
                "risk_factors": [],
                "technologies": [],
            },
        )
