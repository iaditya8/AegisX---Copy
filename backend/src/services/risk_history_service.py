import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import WorkflowEvent
from src.services.audit_service import create_audit_entry


class RiskHistoryService:
    """Service to track and manage in-memory history of asset risk/criticality
    changes, emitting events.
    """

    # In-memory history store mapping asset_id to list of history records
    _history: Dict[uuid.UUID, List[Dict[str, Any]]] = {}

    @classmethod
    async def record_history(
        cls,
        db: AsyncSession,
        asset_id: uuid.UUID,
        new_score: int,
        new_level: str,
        new_criticality: str,
        scan_run_id: Optional[uuid.UUID] = None,
        workflow_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Record the new risk values for an asset. Detects changes compared to the
        latest recorded entry, creates audit logs, and emits workflow events.
        """
        now = datetime.now(timezone.utc)
        asset_history = cls._history.setdefault(asset_id, [])

        old_record = asset_history[-1] if asset_history else None

        # Determine events to emit
        events_to_emit = []

        if old_record is None:
            # First calculation
            events_to_emit.append("risk.calculated")
            # For criticality, emit if first set
            events_to_emit.append("criticality.changed")
        else:
            old_score = old_record["risk_score"]
            old_level = old_record["risk_level"]
            old_criticality = old_record["criticality"]

            if new_score != old_score or new_level != old_level:
                events_to_emit.append("risk.updated")

            if new_score > old_score:
                events_to_emit.append("risk.increased")
            elif new_score < old_score:
                events_to_emit.append("risk.decreased")

            if new_criticality != old_criticality:
                events_to_emit.append("criticality.changed")

        # Create new history record
        new_record = {
            "risk_score": new_score,
            "risk_level": new_level,
            "criticality": new_criticality,
            "timestamp": now.isoformat(),
            "scan_run_id": str(scan_run_id) if scan_run_id else None,
            "workflow_id": str(workflow_id) if workflow_id else None,
        }
        asset_history.append(new_record)

        # Emit audit logs and workflow events
        for event_type in events_to_emit:
            # Create workflow event if workflow context is provided
            if workflow_id:
                event_id = uuid.uuid4()
                evt = WorkflowEvent(
                    id=event_id,
                    workflow_id=workflow_id,
                    event_type=event_type,
                    correlation_id=scan_run_id,
                    payload={
                        "event_id": str(event_id),
                        "correlation_id": str(scan_run_id) if scan_run_id else None,
                        "workflow_id": str(workflow_id),
                        "scan_run_id": str(scan_run_id) if scan_run_id else None,
                        "timestamp": now.isoformat(),
                        "asset_id": str(asset_id),
                        "old_value": old_record if old_record else {},
                        "new_value": new_record,
                    },
                    timestamp=now,
                )
                db.add(evt)

            # Create Audit Log entry
            audit_metadata = {
                "asset_id": str(asset_id),
                "event_type": event_type,
                "old_score": old_record["risk_score"] if old_record else None,
                "new_score": new_score,
                "old_level": old_record["risk_level"] if old_record else None,
                "new_level": new_level,
                "old_criticality": old_record["criticality"] if old_record else None,
                "new_criticality": new_criticality,
                "scan_run_id": str(scan_run_id) if scan_run_id else None,
                "workflow_id": str(workflow_id) if workflow_id else None,
            }
            await create_audit_entry(
                db=db,
                actor_id=None,  # system triggered
                action=event_type,
                target_type="Asset",
                target_id=asset_id,
                metadata=audit_metadata,
            )

        if workflow_id and events_to_emit:
            await db.commit()

        if events_to_emit:
            from src.services.report_cache_service import ReportCacheService

            ReportCacheService.invalidate_for_asset(asset_id)

        return asset_history

    @classmethod
    def get_history(cls, asset_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Retrieve the in-memory history list for an asset."""
        return cls._history.get(asset_id, [])

    @classmethod
    def clear_history(cls) -> None:
        """Clear the history cache (useful for testing)."""
        cls._history.clear()
