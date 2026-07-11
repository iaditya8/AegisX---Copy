import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy.future import select
from src.domain.entities.incident import IncidentSeverity, IncidentStatus
from src.infrastructure.database.models import (
    Incident as DBIncident,
    IntelligenceEvent,
    CorrelationCluster,
    CorrelationClusterSignal,
    Finding,
)
from src.services.incident_service import IncidentRecord, IncidentService
from src.services.incident_fingerprint_service import IncidentFingerprintService
from src.services.incident_history_service import IncidentHistoryService
from src.services.incident_evidence_service import IncidentEvidenceService
from src.services.workflow_event_service import WorkflowEventService
from src.services.correlation_repository_helper import append_history_helper
from src.core.tenant import require_current_tenant_id


class CorrelationIncidentBridge:
    @classmethod
    async def escalate_cluster(
        cls,
        db,
        cluster_id: uuid.UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> DBIncident:
        """Escalate a CorrelationCluster to a formal Incident within the database transaction context."""
        tenant_id = require_current_tenant_id()

        # 1. Load Cluster
        q_cluster = select(CorrelationCluster).filter(
            CorrelationCluster.tenant_id == tenant_id,
            CorrelationCluster.id == cluster_id
        )
        res_cluster = await db.execute(q_cluster)
        cluster = res_cluster.scalar_one_or_none()
        if not cluster:
            raise ValueError(f"CorrelationCluster with ID {cluster_id} not found.")

        if cluster.associated_incident_id:
            raise ValueError(f"CorrelationCluster {cluster_id} is already escalated to incident {cluster.associated_incident_id}.")

        # 2. Extract Signals
        q_signals = select(CorrelationClusterSignal).filter(
            CorrelationClusterSignal.cluster_id == cluster_id
        )
        res_signals = await db.execute(q_signals)
        signals = res_signals.scalars().all()

        alert_ids = [s.signal_id for s in signals if s.signal_type == "alert"]
        finding_ids = [s.signal_id for s in signals if s.signal_type == "finding"]
        asset_ids = [cluster.asset_id]

        # 3. Generate Incident Fingerprint
        fingerprint = IncidentFingerprintService.generate_fingerprint(
            alert_ids, asset_ids, finding_ids
        )

        incident_id = uuid.uuid4()
        inc_title = title or f"Automated Security Incident on Asset {str(cluster.asset_id)[:8]}"
        inc_desc = description or f"Incident automatically escalated from CorrelationCluster {cluster.id} (Unified Score: {cluster.unified_score:.2f})"

        # 4. Create DB Incident Model
        db_inc = DBIncident(
            tenant_id=tenant_id,
            id=incident_id,
            incident_fingerprint=fingerprint,
            title=inc_title,
            description=inc_desc,
            severity="high",
            status="open",
            alert_ids=alert_ids,
            asset_ids=asset_ids,
            finding_ids=finding_ids,
            recommendation_ids=[],
            remediation_ids=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(db_inc)

        # 5. Populate L2 Incident cache
        record = IncidentRecord(
            incident_id=incident_id,
            incident_fingerprint=fingerprint,
            title=inc_title,
            description=inc_desc,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.OPEN,
            alert_ids=alert_ids,
            asset_ids=asset_ids,
            finding_ids=finding_ids,
            recommendation_ids=[],
            remediation_ids=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        IncidentService._incidents[incident_id] = record
        IncidentService._fingerprint_lookup[fingerprint] = incident_id

        # 6. Associate Cluster with Incident
        cluster.associated_incident_id = incident_id
        cluster.status = "triaged"
        cluster.updated_at = datetime.now(timezone.utc)

        # 7. Record History Events (in-memory & db via unit of work helpers if available)
        # For db history, we can instantiate and stage IncidentHistory or use IncidentHistoryService
        from src.infrastructure.database.unit_of_work import UnitOfWork
        from src.infrastructure.repositories import IncidentRepository
        uow = UnitOfWork(require_tenant=False)
        uow.session = db
        uow.incident_repo = IncidentRepository(db)
        await IncidentHistoryService.record_event(
            incident_id=incident_id,
            event_type="CREATED",
            details=f"Incident escalated from CorrelationCluster {cluster.id}.",
            uow=uow
        )

        # 8. Record Cluster History
        await append_history_helper(db, cluster.id, "cluster_escalated", {"incident_id": str(incident_id)})
        await append_history_helper(db, cluster.id, "incident_created", {"incident_id": str(incident_id)})

        # 9. Add evidence logs
        for fid in finding_ids:
            try:
                q_f = select(Finding).filter(Finding.id == fid)
                res_f = await db.execute(q_f)
                finding = res_f.scalar_one_or_none()
                if finding:
                    await IncidentEvidenceService.add_evidence(incident_id, "findings", finding, uow=uow)
            except Exception:
                pass

        # 10. Stage Outbox event
        outbox_evt = IntelligenceEvent(
            tenant_id=tenant_id,
            event_type="incident.open",
            payload={"incident_id": str(incident_id), "status": "OPEN"}
        )
        db.add(outbox_evt)

        # 11. Emit workflow event (stages outbox event atomically)
        await WorkflowEventService.emit_event(
            db=db,
            event_type="correlation.incident_automated",
            correlation_id=incident_id,
            payload={
                "cluster_id": str(cluster.id),
                "incident_id": str(incident_id),
                "unified_score": cluster.unified_score,
            }
        )

        from src.services.incident_snapshot_service import IncidentSnapshotService
        IncidentSnapshotService.invalidate_cache()

        await db.flush()
        return db_inc
