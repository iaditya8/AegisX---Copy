import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.remediation import RemediationHistoryType, RemediationStatus
from src.services.audit_service import create_audit_entry
from src.services.remediation_history_service import RemediationHistoryService
from src.services.remediation_snapshot_service import RemediationSnapshotService
from src.services.workflow_event_service import WorkflowEventService


class ExceptionService:
    @classmethod
    async def apply_exception(
        cls,
        db: AsyncSession,
        remediation: Any,
        new_status: RemediationStatus,
        reason: str,
        approved_by: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Apply an exception policy to a remediation.

        Supported types: ACCEPTED_RISK, FALSE_POSITIVE, or DEFERRED.
        """
        from src.services.remediation_service import RemediationService

        # Validate transition first
        RemediationService.validate_transition(remediation.status, new_status)

        old_status = remediation.status
        remediation.status = new_status
        remediation.reason = reason
        remediation.approved_by = approved_by
        remediation.exception_approved_at = datetime.now(timezone.utc)
        remediation.updated_at = datetime.now(timezone.utc)

        # Record history event
        RemediationHistoryService.record_event(
            remediation_id=remediation.remediation_id,
            history_type=RemediationHistoryType.EXCEPTION,
            old_value={"status": old_status.value},
            new_value={
                "status": new_status.value,
                "reason": reason,
                "approved_by": approved_by,
            },
            actor_id=actor_id,
        )

        # Emit workflow event
        event_name = f"remediation.{new_status.value.lower()}"
        await WorkflowEventService.emit_event(
            db=db,
            event_type=event_name,
            correlation_id=None,
            payload={
                "remediation_id": str(remediation.remediation_id),
                "status": new_status.value,
                "reason": reason,
                "approved_by": approved_by,
            },
        )

        # Record audit log
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action=event_name,
            target_type="remediation",
            target_id=remediation.remediation_id,
            metadata={
                "remediation_id": str(remediation.remediation_id),
                "status": new_status.value,
                "reason": reason,
                "approved_by": approved_by,
            },
        )

        # Update cached snapshot
        RemediationSnapshotService.update_snapshot(remediation.asset_id)
