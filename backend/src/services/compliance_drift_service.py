import uuid
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.governance import GovernanceStatus
from src.infrastructure.database.models import Asset
from src.services.audit_service import create_audit_entry
from src.services.compliance_mapping_service import ComplianceMappingService
from src.services.governance_service import GovernanceService
from src.services.workflow_event_service import WorkflowEventService


class ComplianceDriftService:
    # in-memory cache of last known asset compliance states
    _last_asset_states: Dict[uuid.UUID, GovernanceStatus] = {}
    # in-memory cache of last known compliance control statuses
    _last_control_states: Dict[str, str] = {}

    @classmethod
    def clear_drift_states(cls) -> None:
        """Clear the cached drift states."""
        cls._last_asset_states.clear()
        cls._last_control_states.clear()

    @classmethod
    async def detect_drift(
        cls, db: AsyncSession, actor_id: Optional[uuid.UUID] = None
    ) -> None:
        """Compare current compliance states against last known states and emit events on drift."""
        # 1. Detect Asset Governance drift
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        res_assets = await db.execute(q_assets)
        assets = res_assets.scalars().all()

        for asset in assets:
            current_status = await GovernanceService.evaluate_asset_governance(
                db, asset.id
            )
            old_status = cls._last_asset_states.get(asset.id)

            if old_status is not None and old_status != current_status:
                # Drift occurred!
                if (
                    old_status == GovernanceStatus.COMPLIANT
                    and current_status == GovernanceStatus.NON_COMPLIANT
                ):
                    # Compliant -> Non-Compliant
                    await WorkflowEventService.emit_event(
                        db=db,
                        event_type="governance.non_compliant",
                        payload={
                            "asset_id": str(asset.id),
                            "previous_status": old_status.value,
                            "current_status": current_status.value,
                        },
                    )
                    await create_audit_entry(
                        db=db,
                        actor_id=actor_id,
                        action="governance.non_compliant",
                        target_type="asset",
                        target_id=asset.id,
                        metadata={
                            "asset_id": str(asset.id),
                            "previous_status": old_status.value,
                            "current_status": current_status.value,
                        },
                    )

                elif (
                    old_status == GovernanceStatus.NON_COMPLIANT
                    and current_status == GovernanceStatus.COMPLIANT
                ):
                    # Non-Compliant -> Compliant
                    await WorkflowEventService.emit_event(
                        db=db,
                        event_type="governance.compliant",
                        payload={
                            "asset_id": str(asset.id),
                            "previous_status": old_status.value,
                            "current_status": current_status.value,
                        },
                    )
                    await create_audit_entry(
                        db=db,
                        actor_id=actor_id,
                        action="governance.compliant",
                        target_type="asset",
                        target_id=asset.id,
                        metadata={
                            "asset_id": str(asset.id),
                            "previous_status": old_status.value,
                            "current_status": current_status.value,
                        },
                    )

            # Keep cache updated (only seed if not present)
            cls._last_asset_states[asset.id] = current_status

        # 2. Detect Compliance Control status drift
        controls = await ComplianceMappingService.get_compliance_controls(db)
        for c in controls:
            current_status = c.status
            old_status = cls._last_control_states.get(c.control_id)

            if old_status is not None and old_status != current_status:
                if old_status == "COMPLIANT" and current_status == "NON_COMPLIANT":
                    # Control failed
                    await WorkflowEventService.emit_event(
                        db=db,
                        event_type="compliance.control_failed",
                        payload={
                            "control_id": c.control_id,
                            "control_name": c.control_name,
                            "previous_status": old_status,
                            "current_status": current_status,
                        },
                    )
                    await create_audit_entry(
                        db=db,
                        actor_id=actor_id,
                        action="compliance.control_failed",
                        target_type="compliance_control",
                        target_id=uuid.uuid5(uuid.NAMESPACE_DNS, c.control_id),
                        metadata={
                            "control_id": c.control_id,
                            "control_name": c.control_name,
                        },
                    )

                elif old_status == "NON_COMPLIANT" and current_status == "COMPLIANT":
                    # Control restored
                    await WorkflowEventService.emit_event(
                        db=db,
                        event_type="compliance.control_restored",
                        payload={
                            "control_id": c.control_id,
                            "control_name": c.control_name,
                            "previous_status": old_status,
                            "current_status": current_status,
                        },
                    )
                    await create_audit_entry(
                        db=db,
                        actor_id=actor_id,
                        action="compliance.control_restored",
                        target_type="compliance_control",
                        target_id=uuid.uuid5(uuid.NAMESPACE_DNS, c.control_id),
                        metadata={
                            "control_id": c.control_id,
                            "control_name": c.control_name,
                        },
                    )

            cls._last_control_states[c.control_id] = current_status
