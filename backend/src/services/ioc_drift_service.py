import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.services.ioc_service import IOCService
from src.services.threat_intelligence_snapshot_service import ThreatIntelligenceSnapshotService
from src.services.workflow_event_service import WorkflowEventService


class IOCDriftService:
    @classmethod
    async def check_drift(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None, prev_snapshot: Optional[dict] = None
    ) -> None:
        """Check for threat intelligence drift and reputation updates compared to a previous snapshot."""
        if prev_snapshot is None:
            prev_snapshot = ThreatIntelligenceSnapshotService.get_snapshot(scope_id)

        if not prev_snapshot:
            # First run, no baseline to check drift against
            return

        # Fetch current IOCs
        iocs = IOCService.get_all_iocs()
        if scope_id:
            iocs = [i for i in iocs if i.scope_id == scope_id]

        current_lookup = {str(ioc.ioc_id): ioc for ioc in iocs}
        prev_lookup = prev_snapshot.get("iocs", {})

        # Compare individual IOCs
        for ioc_id_str, prev_ioc in prev_lookup.items():
            current_ioc = current_lookup.get(ioc_id_str)
            if not current_ioc:
                continue

            # Check reputation change
            prev_rep = prev_ioc.get("reputation", 0)
            curr_rep = current_ioc.reputation
            if prev_rep != curr_rep:
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="ioc.reputation_changed",
                    correlation_id=current_ioc.ioc_id,
                    payload={
                        "ioc_id": ioc_id_str,
                        "value": current_ioc.value,
                        "previous_reputation": prev_rep,
                        "current_reputation": curr_rep,
                        "scope_id": str(scope_id) if scope_id else None,
                    },
                )

            # Check attribution changes
            prev_actors = sorted(prev_ioc.get("threat_actors", []))
            curr_actors = sorted(current_ioc.threat_actors)
            prev_campaigns = sorted(prev_ioc.get("campaigns", []))
            curr_campaigns = sorted(current_ioc.campaigns)

            if prev_actors != curr_actors or prev_campaigns != curr_campaigns:
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="ioc.drift",
                    correlation_id=current_ioc.ioc_id,
                    payload={
                        "type": "attribution_changed",
                        "ioc_id": ioc_id_str,
                        "value": current_ioc.value,
                        "previous_actors": prev_actors,
                        "current_actors": curr_actors,
                        "previous_campaigns": prev_campaigns,
                        "current_campaigns": curr_campaigns,
                        "scope_id": str(scope_id) if scope_id else None,
                    },
                )

            # Check severity changes
            prev_sev = prev_ioc.get("severity")
            curr_sev = current_ioc.severity.value
            if prev_sev != curr_sev:
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="ioc.drift",
                    correlation_id=current_ioc.ioc_id,
                    payload={
                        "type": "severity_changed",
                        "ioc_id": ioc_id_str,
                        "value": current_ioc.value,
                        "previous_severity": prev_sev,
                        "current_severity": curr_sev,
                        "scope_id": str(scope_id) if scope_id else None,
                    },
                )
