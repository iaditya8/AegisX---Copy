import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.governance import RiskAcceptanceStatus
from src.domain.entities.remediation import RemediationStatus
from src.services.audit_service import create_audit_entry
from src.services.risk_acceptance_registry import RISK_ACCEPTANCE_DAYS
from src.services.workflow_event_service import WorkflowEventService


class RiskAcceptanceRecord:
    def __init__(
        self,
        acceptance_id: uuid.UUID,
        asset_id: uuid.UUID,
        finding_id: Optional[uuid.UUID],
        recommendation_id: Optional[uuid.UUID],
        recommendation_fingerprint: str,
        approved_by: str,
        approved_at: datetime,
        expiration_date: datetime,
        status: RiskAcceptanceStatus,
        reason: str,
    ):
        self.acceptance_id = acceptance_id
        self.asset_id = asset_id
        self.finding_id = finding_id
        self.recommendation_id = recommendation_id
        self.recommendation_fingerprint = recommendation_fingerprint
        self.approved_by = approved_by
        self.approved_at = approved_at
        self.expiration_date = expiration_date
        self.status = status
        self.reason = reason


class RiskAcceptanceService:
    # in-memory store: acceptance_id -> RiskAcceptanceRecord
    _acceptances: Dict[uuid.UUID, RiskAcceptanceRecord] = {}
    # fingerprint mapping: fingerprint -> list of acceptance_ids
    _fingerprint_acceptances: Dict[str, List[uuid.UUID]] = {}

    @classmethod
    def clear_acceptances(cls) -> None:
        """Clear all in-memory risk acceptances."""
        cls._acceptances.clear()
        cls._fingerprint_acceptances.clear()

    @classmethod
    def get_all_acceptances(cls) -> List[RiskAcceptanceRecord]:
        """Retrieve all risk acceptance records."""
        return list(cls._acceptances.values())

    @classmethod
    def get_acceptance(cls, acceptance_id: uuid.UUID) -> Optional[RiskAcceptanceRecord]:
        """Retrieve a specific risk acceptance."""
        return cls._acceptances.get(acceptance_id)

    @classmethod
    def get_active_acceptances(cls) -> List[RiskAcceptanceRecord]:
        """Retrieve all currently active (or expiring) acceptances."""
        return [
            a
            for a in cls._acceptances.values()
            if a.status in [RiskAcceptanceStatus.ACTIVE, RiskAcceptanceStatus.EXPIRING]
        ]

    @classmethod
    def get_expiring_acceptances(cls) -> List[RiskAcceptanceRecord]:
        """Retrieve all expiring acceptances."""
        return [
            a
            for a in cls._acceptances.values()
            if a.status == RiskAcceptanceStatus.EXPIRING
        ]

    @classmethod
    def get_acceptances_by_asset(
        cls, asset_id: uuid.UUID
    ) -> List[RiskAcceptanceRecord]:
        """Retrieve all acceptances associated with an asset."""
        return [a for a in cls._acceptances.values() if a.asset_id == asset_id]

    @classmethod
    async def accept_risk(
        cls,
        db: AsyncSession,
        asset_id: uuid.UUID,
        finding_id: Optional[uuid.UUID],
        recommendation_id: Optional[uuid.UUID],
        recommendation_fingerprint: str,
        approved_by: str,
        reason: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> RiskAcceptanceRecord:
        """Formally accept risk for a recommendation footprint."""
        from src.services.exception_service import ExceptionService
        from src.services.governance_snapshot_service import GovernanceSnapshotService
        from src.services.remediation_service import RemediationService

        # 1. Determine severity
        severity = "MEDIUM"
        if finding_id:
            from src.infrastructure.database.models import Finding

            finding = await db.get(Finding, finding_id)
            if finding:
                severity = finding.severity.upper()

        # 2. Expiration duration lookup
        days = RISK_ACCEPTANCE_DAYS.get(severity, 90)
        now = datetime.now(timezone.utc)
        expiration_date = now + timedelta(days=days)

        # 3. Handle remediation linkage
        rem_id = RemediationService._fingerprint_lookup.get(recommendation_fingerprint)
        if not rem_id:
            # Sync recommendation first to auto-create the remediation
            title = f"Remediation for {recommendation_fingerprint[:8]}"
            if finding_id:
                from src.infrastructure.database.models import Finding

                finding = await db.get(Finding, finding_id)
                if finding:
                    title = finding.title

            remediation_record = await RemediationService.sync_recommendation(
                db=db,
                fingerprint=recommendation_fingerprint,
                asset_id=asset_id,
                finding_id=finding_id,
                priority=severity,
                title=title,
                actor_id=actor_id,
            )
            rem_id = remediation_record.remediation_id

        remediation = RemediationService.get_remediation(rem_id)
        if not remediation:
            raise ValueError(
                f"Remediation record not found for fingerprint {recommendation_fingerprint}"
            )

        # 4. Apply exception to remediation
        await ExceptionService.apply_exception(
            db=db,
            remediation=remediation,
            new_status=RemediationStatus.ACCEPTED_RISK,
            reason=reason,
            approved_by=approved_by,
            actor_id=actor_id,
        )

        # 5. Revoke any prior active/expiring acceptances for this fingerprint
        existing_ids = cls._fingerprint_acceptances.get(recommendation_fingerprint, [])
        for old_id in existing_ids:
            old_acc = cls._acceptances.get(old_id)
            if old_acc and old_acc.status in [
                RiskAcceptanceStatus.ACTIVE,
                RiskAcceptanceStatus.EXPIRING,
            ]:
                old_acc.status = RiskAcceptanceStatus.REVOKED

        # 6. Create Risk Acceptance Record
        acceptance_id = uuid.uuid4()
        record = RiskAcceptanceRecord(
            acceptance_id=acceptance_id,
            asset_id=asset_id,
            finding_id=finding_id,
            recommendation_id=recommendation_id,
            recommendation_fingerprint=recommendation_fingerprint,
            approved_by=approved_by,
            approved_at=now,
            expiration_date=expiration_date,
            status=RiskAcceptanceStatus.ACTIVE,
            reason=reason,
        )

        cls._acceptances[acceptance_id] = record
        if recommendation_fingerprint not in cls._fingerprint_acceptances:
            cls._fingerprint_acceptances[recommendation_fingerprint] = []
        cls._fingerprint_acceptances[recommendation_fingerprint].append(acceptance_id)

        # 7. Workflow event
        await WorkflowEventService.emit_event(
            db=db,
            event_type="risk_acceptance.created",
            payload={
                "acceptance_id": str(acceptance_id),
                "asset_id": str(asset_id),
                "recommendation_fingerprint": recommendation_fingerprint,
                "status": record.status.value,
            },
        )

        # 8. Audit entry
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="risk_acceptance.created",
            target_type="risk_acceptance",
            target_id=acceptance_id,
            metadata={
                "acceptance_id": str(acceptance_id),
                "asset_id": str(asset_id),
                "recommendation_fingerprint": recommendation_fingerprint,
                "status": record.status.value,
            },
        )

        await GovernanceSnapshotService.update_snapshot(db, asset_id)
        return record

    @classmethod
    async def revoke_risk(
        cls,
        db: AsyncSession,
        acceptance_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> RiskAcceptanceRecord:
        """Revoke an active risk acceptance."""
        from src.services.governance_snapshot_service import GovernanceSnapshotService
        from src.services.remediation_service import RemediationService

        record = cls.get_acceptance(acceptance_id)
        if not record:
            raise ValueError(f"Risk acceptance {acceptance_id} not found")

        if record.status not in [
            RiskAcceptanceStatus.ACTIVE,
            RiskAcceptanceStatus.EXPIRING,
        ]:
            raise ValueError(
                f"Cannot revoke risk acceptance in status {record.status.value}"
            )

        record.status = RiskAcceptanceStatus.REVOKED

        # Revert remediation status back to OPEN
        rem_id = RemediationService._fingerprint_lookup.get(
            record.recommendation_fingerprint
        )
        if rem_id:
            await RemediationService.update_status(
                db=db,
                remediation_id=rem_id,
                status=RemediationStatus.OPEN,
                actor_id=actor_id,
                bypass_terminal=True,
            )

        # Workflow event
        await WorkflowEventService.emit_event(
            db=db,
            event_type="risk_acceptance.revoked",
            payload={
                "acceptance_id": str(acceptance_id),
                "asset_id": str(record.asset_id),
                "recommendation_fingerprint": record.recommendation_fingerprint,
                "status": record.status.value,
            },
        )

        # Audit entry
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="risk_acceptance.revoked",
            target_type="risk_acceptance",
            target_id=acceptance_id,
            metadata={
                "acceptance_id": str(acceptance_id),
                "asset_id": str(record.asset_id),
                "recommendation_fingerprint": record.recommendation_fingerprint,
                "status": record.status.value,
            },
        )

        await GovernanceSnapshotService.update_snapshot(db, record.asset_id)
        return record

    @classmethod
    async def expire_risk(
        cls,
        db: AsyncSession,
        acceptance_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> RiskAcceptanceRecord:
        """Force expire a risk acceptance."""
        from src.services.governance_snapshot_service import GovernanceSnapshotService
        from src.services.remediation_service import RemediationService

        record = cls.get_acceptance(acceptance_id)
        if not record:
            raise ValueError(f"Risk acceptance {acceptance_id} not found")

        record.status = RiskAcceptanceStatus.EXPIRED

        # Revert remediation status back to OPEN
        rem_id = RemediationService._fingerprint_lookup.get(
            record.recommendation_fingerprint
        )
        if rem_id:
            await RemediationService.update_status(
                db=db,
                remediation_id=rem_id,
                status=RemediationStatus.OPEN,
                actor_id=actor_id,
                bypass_terminal=True,
            )

        # Workflow event
        await WorkflowEventService.emit_event(
            db=db,
            event_type="risk_acceptance.expired",
            payload={
                "acceptance_id": str(acceptance_id),
                "asset_id": str(record.asset_id),
                "recommendation_fingerprint": record.recommendation_fingerprint,
                "status": record.status.value,
            },
        )

        # Audit entry
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="risk_acceptance.expired",
            target_type="risk_acceptance",
            target_id=acceptance_id,
            metadata={
                "acceptance_id": str(acceptance_id),
                "asset_id": str(record.asset_id),
                "recommendation_fingerprint": record.recommendation_fingerprint,
                "status": record.status.value,
            },
        )

        await GovernanceSnapshotService.update_snapshot(db, record.asset_id)
        return record

    @classmethod
    async def check_expirations(
        cls,
        db: AsyncSession,
        actor_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Evaluate all risk acceptances, update states for expiring and expired policies."""
        from src.services.governance_snapshot_service import GovernanceSnapshotService
        from src.services.remediation_service import RemediationService

        now = datetime.now(timezone.utc)
        for record in list(cls._acceptances.values()):
            if record.status not in [
                RiskAcceptanceStatus.ACTIVE,
                RiskAcceptanceStatus.EXPIRING,
            ]:
                continue

            time_remaining = record.expiration_date - now

            if time_remaining <= timedelta(seconds=0):
                # Expired!
                record.status = RiskAcceptanceStatus.EXPIRED

                # Revert remediation status back to OPEN
                rem_id = RemediationService._fingerprint_lookup.get(
                    record.recommendation_fingerprint
                )
                if rem_id:
                    await RemediationService.update_status(
                        db=db,
                        remediation_id=rem_id,
                        status=RemediationStatus.OPEN,
                        actor_id=actor_id,
                        bypass_terminal=True,
                    )

                # Event and audit
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="risk_acceptance.expired",
                    payload={
                        "acceptance_id": str(record.acceptance_id),
                        "asset_id": str(record.asset_id),
                        "recommendation_fingerprint": record.recommendation_fingerprint,
                        "status": record.status.value,
                    },
                )
                await create_audit_entry(
                    db=db,
                    actor_id=actor_id,
                    action="risk_acceptance.expired",
                    target_type="risk_acceptance",
                    target_id=record.acceptance_id,
                    metadata={
                        "acceptance_id": str(record.acceptance_id),
                        "asset_id": str(record.asset_id),
                        "recommendation_fingerprint": record.recommendation_fingerprint,
                    },
                )
                await GovernanceSnapshotService.update_snapshot(db, record.asset_id)

            elif (
                time_remaining <= timedelta(days=7)
                and record.status == RiskAcceptanceStatus.ACTIVE
            ):
                # Transitioning from ACTIVE to EXPIRING
                record.status = RiskAcceptanceStatus.EXPIRING

                # Event and audit
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="risk_acceptance.expiring",
                    payload={
                        "acceptance_id": str(record.acceptance_id),
                        "asset_id": str(record.asset_id),
                        "recommendation_fingerprint": record.recommendation_fingerprint,
                        "status": record.status.value,
                    },
                )
                await create_audit_entry(
                    db=db,
                    actor_id=actor_id,
                    action="risk_acceptance.expiring",
                    target_type="risk_acceptance",
                    target_id=record.acceptance_id,
                    metadata={
                        "acceptance_id": str(record.acceptance_id),
                        "asset_id": str(record.asset_id),
                        "recommendation_fingerprint": record.recommendation_fingerprint,
                    },
                )
                await GovernanceSnapshotService.update_snapshot(db, record.asset_id)
