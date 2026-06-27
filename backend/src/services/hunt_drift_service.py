import uuid
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.services.hunt_service import HuntService
from src.services.hunt_coverage_service import HuntCoverageService
from src.services.workflow_event_service import WorkflowEventService


class HuntDriftService:
    @classmethod
    async def check_drift(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None, prev_snapshot: Optional[dict] = None
    ) -> None:
        """Evaluate posture and coverage changes to emit hunt events."""
        if not prev_snapshot:
            return

        # 1. Fetch current hunts
        hunts = HuntService.get_all_hunts()
        if scope_id:
            hunts = [h for h in hunts if h.scope_id == scope_id]

        current_lookup = {str(h.hunt_id): h for h in hunts}
        prev_hunts = prev_snapshot.get("hunts", {})

        # Compare individual hunt records for status/severity/owner changes
        for hunt_id_str, prev_h in prev_hunts.items():
            current_h = current_lookup.get(hunt_id_str)
            if not current_h:
                continue

            prev_status = prev_h.get("status")
            curr_status = current_h.status.value
            prev_sev = prev_h.get("severity")
            curr_sev = current_h.severity.value
            prev_owner = prev_h.get("owner_id")
            curr_owner = str(current_h.owner_id) if current_h.owner_id else None

            if prev_status != curr_status or prev_sev != curr_sev or prev_owner != curr_owner:
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="hunt.drift",
                    correlation_id=current_h.hunt_id,
                    payload={
                        "hunt_id": hunt_id_str,
                        "title": current_h.title,
                        "previous_status": prev_status,
                        "current_status": curr_status,
                        "previous_severity": prev_sev,
                        "current_severity": curr_sev,
                        "previous_owner": prev_owner,
                        "current_owner": curr_owner,
                        "scope_id": str(scope_id) if scope_id else None,
                    },
                )

        # 2. Check coverage drift
        current_coverage = HuntCoverageService.calculate_coverage(scope_id)
        prev_coverage = prev_snapshot.get("coverage", {})

        if prev_coverage:
            changed = False
            for k in ["attack_coverage", "ioc_coverage", "actor_coverage", "campaign_coverage"]:
                if prev_coverage.get(k) != current_coverage.get(k):
                    changed = True
                    break

            if changed:
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="hunt.coverage_changed",
                    payload={
                        "previous_coverage": prev_coverage,
                        "current_coverage": current_coverage,
                        "scope_id": str(scope_id) if scope_id else None,
                    },
                )
