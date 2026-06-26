import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.case import CaseSeverity, CaseStatus
from src.infrastructure.database.models import Asset
from src.services.audit_service import create_audit_entry
from src.services.case_fingerprint_service import CaseFingerprintService
from src.services.case_history_service import CaseHistoryService
from src.services.case_severity_registry import CaseSeverityRegistry
from src.services.case_snapshot_service import CaseSnapshotService
from src.services.incident_service import IncidentService
from src.services.workflow_event_service import WorkflowEventService


class CaseRecord:
    def __init__(
        self,
        case_id: uuid.UUID,
        case_fingerprint: str,
        title: str,
        description: str,
        severity: CaseSeverity,
        status: CaseStatus,
        owner: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        incident_ids: Optional[List[uuid.UUID]] = None,
        alert_ids: Optional[List[uuid.UUID]] = None,
        asset_ids: Optional[List[uuid.UUID]] = None,
    ):
        self.case_id = case_id
        self.case_fingerprint = case_fingerprint
        self.title = title
        self.description = description
        self.severity = severity
        self.status = status
        self.owner = owner
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
        self.incident_ids = incident_ids or []
        self.alert_ids = alert_ids or []
        self.asset_ids = asset_ids or []


class CaseService:
    # In-memory store of cases
    _cases: Dict[uuid.UUID, CaseRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def clear_cases(cls) -> None:
        """Clear all in-memory case records and references."""
        cls._cases.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_cases(cls) -> List[CaseRecord]:
        """Retrieve all cases from store."""
        return list(cls._cases.values())

    @classmethod
    def get_case(cls, case_id: uuid.UUID) -> Optional[CaseRecord]:
        """Retrieve a case by ID."""
        return cls._cases.get(case_id)

    @classmethod
    def get_case_by_fingerprint(cls, fingerprint: str) -> Optional[CaseRecord]:
        """Retrieve a case by its stable fingerprint."""
        case_id = cls._fingerprint_lookup.get(fingerprint)
        if case_id:
            return cls.get_case(case_id)
        return None

    @classmethod
    def validate_transition(
        cls, old_status: CaseStatus, new_status: CaseStatus
    ) -> None:
        """Enforce strict case state machine transitions."""
        if old_status == new_status:
            return

        # CLOSED is strictly terminal
        if old_status == CaseStatus.CLOSED:
            raise ValueError("Case is CLOSED and cannot be mutated or reopened.")

        valid_transitions = {
            CaseStatus.OPEN: [CaseStatus.ACTIVE],
            CaseStatus.ACTIVE: [CaseStatus.UNDER_REVIEW, CaseStatus.ESCALATED],
            CaseStatus.UNDER_REVIEW: [CaseStatus.RESOLVED, CaseStatus.ACTIVE],
            CaseStatus.ESCALATED: [CaseStatus.ACTIVE],
            CaseStatus.RESOLVED: [CaseStatus.CLOSED],
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
        case_id: uuid.UUID,
        new_status: CaseStatus,
        actor_id: Optional[uuid.UUID] = None,
    ) -> CaseRecord:
        """Execute a state status transition for a case."""
        case = cls.get_case(case_id)
        if not case:
            raise ValueError(f"Case with ID {case_id} not found.")

        if isinstance(new_status, str):
            new_status = CaseStatus(new_status)

        cls.validate_transition(case.status, new_status)

        old_status = case.status
        case.status = new_status
        case.updated_at = datetime.now(timezone.utc)

        # Record event in immutable history log
        CaseHistoryService.record_event(
            case_id=case_id,
            event_type=new_status.value,
            details=f"Status transitioned from {old_status.value} to {new_status.value}.",
        )

        # Emit workflow event
        await WorkflowEventService.emit_event(
            db=db,
            event_type=f"case.{new_status.value.lower()}",
            payload={
                "case_id": str(case_id),
                "old_status": old_status.value,
                "new_status": new_status.value,
            },
        )

        # Log audit entry
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="case.status_change",
            target_type="case",
            target_id=case_id,
            metadata={
                "old_status": old_status.value,
                "new_status": new_status.value,
            },
        )

        CaseSnapshotService.invalidate_cache()
        return case

    @classmethod
    async def assign_case(
        cls,
        db: AsyncSession,
        case_id: uuid.UUID,
        owner_id: Optional[uuid.UUID],
        actor_id: Optional[uuid.UUID] = None,
    ) -> CaseRecord:
        """Assign case to an analyst/owner."""
        case = cls.get_case(case_id)
        if not case:
            raise ValueError(f"Case with ID {case_id} not found.")

        # Enforce Closed Case Enforcement
        if case.status == CaseStatus.CLOSED:
            raise ValueError("Case is CLOSED and cannot be modified.")

        old_owner = case.owner
        case.owner = owner_id
        case.updated_at = datetime.now(timezone.utc)

        # Record assignment log in immutable history
        CaseHistoryService.record_event(
            case_id=case_id,
            event_type="ASSIGNED",
            details=f"Owner changed from {old_owner} to {owner_id}.",
        )

        # Log audit entry
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="case.assign",
            target_type="case",
            target_id=case_id,
            metadata={
                "old_owner": str(old_owner) if old_owner else None,
                "new_owner": str(owner_id) if owner_id else None,
            },
        )

        CaseSnapshotService.invalidate_cache()
        return case

    @classmethod
    async def sync_cases(cls, db: AsyncSession) -> None:
        """Group active incidents and synchronize them into cases."""
        active_incidents = [
            inc
            for inc in IncidentService.get_all_incidents()
            if inc.status.value != "CLOSED"
        ]

        # Group incidents by asset_id; if no assets, group separately
        asset_to_incidents = {}
        no_asset_incidents = []

        for inc in active_incidents:
            if inc.asset_ids:
                for asset_id in inc.asset_ids:
                    asset_to_incidents.setdefault(asset_id, []).append(inc)
            else:
                no_asset_incidents.append(inc)

        groups = []
        visited_incidents = set()

        for asset_id, group_incidents in asset_to_incidents.items():
            unvisited = [
                inc
                for inc in group_incidents
                if inc.incident_id not in visited_incidents
            ]
            if unvisited:
                for inc in unvisited:
                    visited_incidents.add(inc.incident_id)
                groups.append((asset_id, unvisited))

        for inc in no_asset_incidents:
            if inc.incident_id not in visited_incidents:
                visited_incidents.add(inc.incident_id)
                groups.append((None, [inc]))

        for asset_id, group_incidents in groups:
            incident_ids = [inc.incident_id for inc in group_incidents]
            alert_ids = list(
                set([aid for inc in group_incidents for aid in inc.alert_ids])
            )
            asset_ids = list(
                set([aid for inc in group_incidents for aid in inc.asset_ids])
            )

            fingerprint = CaseFingerprintService.generate_fingerprint(
                incident_ids, alert_ids, asset_ids
            )

            # Preserve identity if fingerprint matches
            existing = cls.get_case_by_fingerprint(fingerprint)
            if existing:
                continue

            case_id = uuid.uuid4()
            severity = CaseSeverityRegistry.calculate_severity(
                [inc.severity for inc in group_incidents]
            )

            # Resolve title using asset host/ip if possible
            title = f"Security Case for Asset: {asset_id}"
            if asset_id:
                try:
                    db_asset = await db.get(Asset, asset_id)
                    if db_asset:
                        name = db_asset.host or db_asset.ip or str(asset_id)[:8]
                        title = f"Security Case for Asset: {name}"
                except Exception:
                    pass
            else:
                title = f"Security Case: {group_incidents[0].title}"

            desc_lines = [
                f"- {inc.title}: {inc.description}" for inc in group_incidents
            ]
            description = "Case aggregated from active incidents:\n" + "\n".join(
                desc_lines
            )

            record = CaseRecord(
                case_id=case_id,
                case_fingerprint=fingerprint,
                title=title,
                description=description,
                severity=severity,
                status=CaseStatus.OPEN,
                owner=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                incident_ids=incident_ids,
                alert_ids=alert_ids,
                asset_ids=asset_ids,
            )

            cls._cases[case_id] = record
            cls._fingerprint_lookup[fingerprint] = case_id

            # Log history event
            CaseHistoryService.record_event(
                case_id=case_id,
                event_type="CREATED",
                details=f"Case automatically created from incidents via sync. Fingerprint: {fingerprint}",
            )

            # Emit workflow event
            await WorkflowEventService.emit_event(
                db=db,
                event_type="case.created",
                payload={"case_id": str(case_id)},
            )

            # Log audit entry
            await create_audit_entry(
                db=db,
                actor_id=None,
                action="case.create",
                target_type="case",
                target_id=case_id,
                metadata={"fingerprint": fingerprint},
            )

        CaseSnapshotService.invalidate_cache()
