import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.incident import (
    IncidentSeverity,
    IncidentStatus,
)
from src.infrastructure.database.models import Asset, Finding, Incident as DBIncident, IntelligenceEvent
from src.services.alert_lifecycle_service import AlertLifecycleService
from src.services.audit_service import create_audit_entry
from src.services.incident_evidence_service import IncidentEvidenceService
from src.services.incident_fingerprint_service import IncidentFingerprintService
from src.services.incident_history_service import IncidentHistoryService
from src.services.incident_severity_registry import IncidentSeverityRegistry
from src.services.workflow_event_service import WorkflowEventService
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.core.tenant import get_current_tenant_id


class IncidentRecord:
    def __init__(
        self,
        incident_id: uuid.UUID,
        incident_fingerprint: str,
        title: str,
        description: str,
        severity: IncidentSeverity,
        status: IncidentStatus,
        owner: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        alert_ids: Optional[List[uuid.UUID]] = None,
        asset_ids: Optional[List[uuid.UUID]] = None,
        finding_ids: Optional[List[uuid.UUID]] = None,
        recommendation_ids: Optional[List[uuid.UUID]] = None,
        remediation_ids: Optional[List[uuid.UUID]] = None,
    ):
        self.incident_id = incident_id
        self.incident_fingerprint = incident_fingerprint
        self.title = title
        self.description = description
        self.severity = severity
        self.status = status
        self.owner = owner
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
        self.alert_ids = alert_ids or []
        self.asset_ids = asset_ids or []
        self.finding_ids = finding_ids or []
        self.recommendation_ids = recommendation_ids or []
        self.remediation_ids = remediation_ids or []
        from src.core.tenant import get_current_tenant_id
        self.tenant_id = get_current_tenant_id()


class IncidentService:
    # Warm L2 cache
    _incidents: Dict[uuid.UUID, IncidentRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def clear_incidents(cls) -> None:
        """Clear all in-memory incident records."""
        cls._incidents.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    async def bootstrap(cls, db: AsyncSession) -> None:
        """Bootstrap the L2 cache from PostgreSQL database."""
        cls.clear_incidents()
        async with UnitOfWork() as uow:
            db_incidents = await uow.incident_repo.list()
            for db_inc in db_incidents:
                record = IncidentRecord(
                    incident_id=db_inc.id,
                    incident_fingerprint=db_inc.incident_fingerprint,
                    title=db_inc.title,
                    description=db_inc.description,
                    severity=IncidentSeverity(db_inc.severity),
                    status=IncidentStatus(db_inc.status),
                    owner=db_inc.owner,
                    created_at=db_inc.created_at,
                    updated_at=db_inc.updated_at,
                    alert_ids=db_inc.alert_ids,
                    asset_ids=db_inc.asset_ids,
                    finding_ids=db_inc.finding_ids,
                    recommendation_ids=db_inc.recommendation_ids,
                    remediation_ids=db_inc.remediation_ids,
                )
                cls._incidents[db_inc.id] = record
                cls._fingerprint_lookup[db_inc.incident_fingerprint] = db_inc.id

                # Load history and evidence cache
                db_histories = await uow.incident_repo.list_history(db_inc.id)
                for db_hist in db_histories:
                    IncidentHistoryService._add_to_cache(db_inc.id, db_hist)

                db_evidences = await uow.incident_repo.list_evidence(db_inc.id)
                for db_ev in db_evidences:
                    IncidentEvidenceService._add_to_cache(db_inc.id, db_ev.category, db_ev)

    @classmethod
    def get_all_incidents(cls) -> List[IncidentRecord]:
        """Retrieve all incidents from store."""
        return list(cls._incidents.values())

    @classmethod
    def get_incident(cls, incident_id: uuid.UUID) -> Optional[IncidentRecord]:
        """Retrieve an incident by ID."""
        return cls._incidents.get(incident_id)

    @classmethod
    def get_incident_by_fingerprint(cls, fingerprint: str) -> Optional[IncidentRecord]:
        """Retrieve an incident by fingerprint."""
        incident_id = cls._fingerprint_lookup.get(fingerprint)
        if incident_id:
            return cls.get_incident(incident_id)
        return None

    @classmethod
    def validate_transition(
        cls, old_status: IncidentStatus, new_status: IncidentStatus
    ) -> None:
        """Enforce the strict incident state machine transitions."""
        if old_status == new_status:
            return

        if old_status == IncidentStatus.CLOSED:
            raise ValueError("Incident is CLOSED and cannot be mutated or reopened.")

        valid_transitions = {
            IncidentStatus.OPEN: [IncidentStatus.TRIAGED, IncidentStatus.ESCALATED],
            IncidentStatus.TRIAGED: [
                IncidentStatus.INVESTIGATING,
                IncidentStatus.ESCALATED,
            ],
            IncidentStatus.INVESTIGATING: [
                IncidentStatus.CONTAINED,
                IncidentStatus.ESCALATED,
            ],
            IncidentStatus.ESCALATED: [
                IncidentStatus.INVESTIGATING,
                IncidentStatus.CONTAINED,
            ],
            IncidentStatus.CONTAINED: [IncidentStatus.RESOLVED],
            IncidentStatus.RESOLVED: [IncidentStatus.CLOSED],
        }

        allowed = valid_transitions.get(old_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition from {old_status.value} to {new_status.value}"
            )

    @classmethod
    async def transition_status(
        cls,
        db: AsyncSession,
        incident_id: uuid.UUID,
        new_status: IncidentStatus,
        actor_id: Optional[uuid.UUID] = None,
    ) -> IncidentRecord:
        """Execute a state status transition for an incident."""
        incident = cls.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident with ID {incident_id} not found.")

        if isinstance(new_status, str):
            new_status = IncidentStatus(new_status)

        cls.validate_transition(incident.status, new_status)

        old_status = incident.status
        incident.status = new_status
        incident.updated_at = datetime.now(timezone.utc)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_inc = await uow.incident_repo.get(incident_id)
            if not db_inc:
                db_inc = DBIncident(
                    tenant_id=tenant_id,
                    id=incident_id,
                    incident_fingerprint=incident.incident_fingerprint,
                    title=incident.title,
                    description=incident.description,
                    severity=incident.severity.value if hasattr(incident.severity, "value") else str(incident.severity),
                    status=old_status.value if hasattr(old_status, "value") else str(old_status),
                    alert_ids=incident.alert_ids,
                    asset_ids=incident.asset_ids,
                    finding_ids=incident.finding_ids,
                    recommendation_ids=incident.recommendation_ids,
                    remediation_ids=incident.remediation_ids,
                )
                await uow.incident_repo.save(db_inc)
            
            db_inc.status = new_status.value
            db_inc.updated_at = incident.updated_at
            db_inc.updated_by = actor_id
                
            # Record event in immutable history log
            await IncidentHistoryService.record_event(
                incident_id=incident_id,
                event_type=(
                    new_status.value
                    if new_status != IncidentStatus.INVESTIGATING
                    else "INVESTIGATION_STARTED"
                ),
                details=f"Status transitioned from {old_status.value} to {new_status.value}.",
                uow=uow,
            )

            # Stage outbox event
            outbox_evt = IntelligenceEvent(
                tenant_id=tenant_id,
                event_type=f"incident.{new_status.value.lower()}",
                payload={
                    "incident_id": str(incident_id),
                    "old_status": old_status.value,
                    "new_status": new_status.value,
                }
            )
            uow.session.add(outbox_evt)
            await uow.commit()

        # Emit workflow event
        await WorkflowEventService.emit_event(
            db=db,
            event_type=f"incident.{new_status.value.lower()}",
            payload={
                "incident_id": str(incident_id),
                "old_status": old_status.value,
                "new_status": new_status.value,
            },
        )

        # Log audit log entry
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="incident.status_change",
            target_type="incident",
            target_id=incident_id,
            metadata={
                "old_status": old_status.value,
                "new_status": new_status.value,
            },
        )

        from src.services.incident_snapshot_service import IncidentSnapshotService
        IncidentSnapshotService.invalidate_cache()

        return incident

    @classmethod
    async def assign_incident(
        cls,
        db: AsyncSession,
        incident_id: uuid.UUID,
        owner_id: Optional[uuid.UUID],
        actor_id: Optional[uuid.UUID] = None,
    ) -> IncidentRecord:
        """Assign incident to an analyst/owner."""
        incident = cls.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident with ID {incident_id} not found.")

        if incident.status == IncidentStatus.CLOSED:
            raise ValueError("Incident is CLOSED and cannot be modified.")

        old_owner = incident.owner
        incident.owner = owner_id
        incident.updated_at = datetime.now(timezone.utc)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_inc = await uow.incident_repo.get(incident_id)
            if not db_inc:
                db_inc = DBIncident(
                    tenant_id=tenant_id,
                    id=incident_id,
                    incident_fingerprint=incident.incident_fingerprint,
                    title=incident.title,
                    description=incident.description,
                    severity=incident.severity.value if hasattr(incident.severity, "value") else str(incident.severity),
                    status=incident.status.value if hasattr(incident.status, "value") else str(incident.status),
                    alert_ids=incident.alert_ids,
                    asset_ids=incident.asset_ids,
                    finding_ids=incident.finding_ids,
                    recommendation_ids=incident.recommendation_ids,
                    remediation_ids=incident.remediation_ids,
                )
                await uow.incident_repo.save(db_inc)
            
            db_inc.owner = owner_id
            db_inc.updated_at = incident.updated_at
            db_inc.updated_by = actor_id

            # Record assignment log in immutable history
            await IncidentHistoryService.record_event(
                incident_id=incident_id,
                event_type="ASSIGNED",
                details=f"Owner changed from {old_owner} to {owner_id}.",
                uow=uow,
            )

            # Stage outbox event
            outbox_evt = IntelligenceEvent(
                tenant_id=tenant_id,
                event_type="incident.assigned",
                payload={
                    "incident_id": str(incident_id),
                    "old_owner": str(old_owner) if old_owner else None,
                    "new_owner": str(owner_id) if owner_id else None,
                }
            )
            uow.session.add(outbox_evt)
            await uow.commit()

        # Log audit entry
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="incident.assign",
            target_type="incident",
            target_id=incident_id,
            metadata={
                "old_owner": str(old_owner) if old_owner else None,
                "new_owner": str(owner_id) if owner_id else None,
            },
        )

        from src.services.incident_snapshot_service import IncidentSnapshotService
        IncidentSnapshotService.invalidate_cache()

        return incident

    @classmethod
    async def sync_alerts(cls, db: AsyncSession) -> None:
        """Group all active alerts into unified incidents and reconcile them."""
        alerts = AlertLifecycleService.get_all_alerts()
        active_alerts = [
            a for a in alerts if a.status.value not in ["RESOLVED", "SUPPRESSED"]
        ]

        asset_groups: Dict[Optional[uuid.UUID], List[Any]] = {}
        no_asset_alerts = []

        for a in active_alerts:
            if a.asset_id:
                asset_groups.setdefault(a.asset_id, []).append(a)
            else:
                no_asset_alerts.append(a)

        groups = []
        for asset_id, grouped in asset_groups.items():
            groups.append((asset_id, grouped))
        for na_alert in no_asset_alerts:
            groups.append((None, [na_alert]))

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        for asset_id, group_alerts in groups:
            alert_ids = [a.alert_id for a in group_alerts]
            finding_ids = list(
                set([a.finding_id for a in group_alerts if a.finding_id])
            )
            recommendation_ids = list(
                set([a.recommendation_id for a in group_alerts if a.recommendation_id])
            )
            remediation_ids = list(
                set([a.remediation_id for a in group_alerts if a.remediation_id])
            )
            asset_ids = [asset_id] if asset_id else []

            fingerprint = IncidentFingerprintService.generate_fingerprint(
                alert_ids, asset_ids, finding_ids
            )

            existing = cls.get_incident_by_fingerprint(fingerprint)
            if existing:
                continue

            incident_id = uuid.uuid4()
            severity = IncidentSeverityRegistry.calculate_severity(
                [a.severity for a in group_alerts]
            )

            title = f"Security Incident on Asset: {asset_id}"
            if asset_id:
                try:
                    db_asset = await db.get(Asset, asset_id)
                    if db_asset:
                        name = db_asset.host or db_asset.ip or str(asset_id)[:8]
                        title = f"Security Incident on Asset: {name}"
                except Exception:
                    pass
            else:
                title = f"Security Incident: {group_alerts[0].title}"

            desc_lines = [f"- {a.title}: {a.description}" for a in group_alerts]
            description = "Incident aggregated from active alerts:\n" + "\n".join(
                desc_lines
            )

            record = IncidentRecord(
                incident_id=incident_id,
                incident_fingerprint=fingerprint,
                title=title,
                description=description,
                severity=severity,
                status=IncidentStatus.OPEN,
                alert_ids=alert_ids,
                asset_ids=asset_ids,
                finding_ids=finding_ids,
                recommendation_ids=recommendation_ids,
                remediation_ids=remediation_ids,
            )

            cls._incidents[incident_id] = record
            cls._fingerprint_lookup[fingerprint] = incident_id

            async with UnitOfWork() as uow:
                db_inc = DBIncident(
                    tenant_id=tenant_id,
                    id=incident_id,
                    incident_fingerprint=fingerprint,
                    title=title,
                    description=description,
                    severity=severity.value,
                    status=IncidentStatus.OPEN.value,
                    alert_ids=alert_ids,
                    asset_ids=asset_ids,
                    finding_ids=finding_ids,
                    recommendation_ids=recommendation_ids,
                    remediation_ids=remediation_ids,
                )
                await uow.incident_repo.save(db_inc)

                # Append CREATED event to history in DB
                await IncidentHistoryService.record_event(
                    incident_id=incident_id,
                    event_type="CREATED",
                    details=f"Incident initialized from alerts: {', '.join([str(aid) for aid in alert_ids])}.",
                    uow=uow,
                )

                # Add read-only evidence references to evidence store in DB
                for a in group_alerts:
                    await IncidentEvidenceService.add_evidence(incident_id, "alerts", a, uow=uow)

                if asset_id:
                    try:
                        db_asset = await db.get(Asset, asset_id)
                        if db_asset:
                            await IncidentEvidenceService.add_evidence(
                                incident_id, "assets", db_asset, uow=uow
                            )
                    except Exception:
                        pass

                for fid in finding_ids:
                    try:
                        db_finding = await db.get(Finding, fid)
                        if db_finding:
                            await IncidentEvidenceService.add_evidence(
                                incident_id, "findings", db_finding, uow=uow
                            )
                    except Exception:
                        pass

                from src.services.remediation_service import RemediationService
                for rmid in remediation_ids:
                    rem = RemediationService.get_remediation(rmid)
                    if rem:
                        await IncidentEvidenceService.add_evidence(
                            incident_id, "remediations", rem, uow=uow
                        )

                # Stage outbox event
                outbox_evt = IntelligenceEvent(
                    tenant_id=tenant_id,
                    event_type="incident.open",
                    payload={"incident_id": str(incident_id), "status": "OPEN"}
                )
                uow.session.add(outbox_evt)
                await uow.commit()

            # Emit workflow event
            await WorkflowEventService.emit_event(
                db=db,
                event_type="incident.open",
                payload={"incident_id": str(incident_id), "status": "OPEN"},
            )

            # Audit entry
            await create_audit_entry(
                db=db,
                actor_id=None,
                action="incident.create",
                target_type="incident",
                target_id=incident_id,
                metadata={"severity": severity.value, "alerts_count": len(alert_ids)},
            )

        from src.services.incident_snapshot_service import IncidentSnapshotService
        IncidentSnapshotService.invalidate_cache()
