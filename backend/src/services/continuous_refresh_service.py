import json
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Asset, Finding


class ContinuousRefreshService:
    _events: List[Any] = []
    _fingerprints: Set[str] = set()

    @classmethod
    def get_all_events(cls) -> List[Any]:
        """Retrieve all emitted monitoring events."""
        return cls._events

    @classmethod
    def clear_events(cls) -> None:
        """Clear all in-memory events and fingerprints."""
        cls._events.clear()
        cls._fingerprints.clear()

    @classmethod
    async def emit_event(
        cls,
        db: AsyncSession,
        change_type: str,
        asset_id: uuid.UUID,
        finding_id: Optional[uuid.UUID],
        previous_state: Optional[str],
        current_state: Optional[str],
        actor_id: Optional[uuid.UUID] = None,
    ) -> Optional[Any]:
        """Verify fingerprint and append new monitoring event."""
        from src.domain.entities.monitoring import MonitoringEvent
        from src.services.audit_service import create_audit_entry
        from src.services.monitoring_fingerprint_service import (
            MonitoringFingerprintService,
        )
        from src.services.workflow_event_service import WorkflowEventService

        fingerprint = MonitoringFingerprintService.calculate_fingerprint(
            change_type=change_type,
            asset_id=str(asset_id),
            finding_id=str(finding_id) if finding_id else None,
            previous_state=previous_state,
            current_state=current_state,
        )

        if fingerprint in cls._fingerprints:
            for event in cls._events:
                if event.fingerprint == fingerprint:
                    return event
            return None

        event_id = uuid.uuid4()
        event = MonitoringEvent(
            event_id=event_id,
            change_type=change_type,
            asset_id=asset_id,
            finding_id=finding_id,
            previous_state=previous_state,
            current_state=current_state,
            timestamp=datetime.now(timezone.utc),
            fingerprint=fingerprint,
        )

        cls._events.append(event)
        cls._fingerprints.add(fingerprint)

        # Trigger workflow event
        await WorkflowEventService.emit_event(
            db=db,
            event_type=f"monitoring.{change_type.lower()}",
            payload={
                "event_id": str(event_id),
                "change_type": change_type,
                "asset_id": str(asset_id),
                "finding_id": str(finding_id) if finding_id else None,
                "previous_state": previous_state,
                "current_state": current_state,
            },
        )

        # Log audit entry
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action=f"monitoring.{change_type.lower()}",
            target_type="asset",
            target_id=asset_id,
            metadata={
                "event_id": str(event_id),
                "change_type": change_type,
                "finding_id": str(finding_id) if finding_id else None,
            },
        )

        return event

    @classmethod
    async def refresh_all(
        cls, db: AsyncSession, actor_id: Optional[uuid.UUID] = None
    ) -> None:
        """Query DB and compare with baselines, generating drift events."""
        from src.domain.entities.governance import GovernanceStatus
        from src.services.asset_risk_snapshot_service import AssetRiskSnapshotService
        from src.services.baseline_state_service import BaselineStateService
        from src.services.governance_service import GovernanceService

        # 1. Fetch active assets
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        res_assets = await db.execute(q_assets)
        assets = res_assets.scalars().all()

        active_asset_ids = {asset.id for asset in assets}

        # Check added & modified assets
        for asset in assets:
            current_state_dict = {
                "host": asset.host,
                "ip": asset.ip,
                "asset_type": asset.asset_type,
            }
            current_state_str = json.dumps(current_state_dict)

            old_baseline = BaselineStateService.get_asset_baseline(asset.id)
            if old_baseline is None:
                # ASSET_ADDED
                await cls.emit_event(
                    db=db,
                    change_type="ASSET_ADDED",
                    asset_id=asset.id,
                    finding_id=None,
                    previous_state=None,
                    current_state=current_state_str,
                    actor_id=actor_id,
                )
                BaselineStateService.capture_asset_baseline(
                    asset.id, current_state_dict
                )
            else:
                if (
                    old_baseline.get("host") != asset.host
                    or old_baseline.get("ip") != asset.ip
                    or old_baseline.get("asset_type") != asset.asset_type
                ):
                    # ASSET_MODIFIED
                    await cls.emit_event(
                        db=db,
                        change_type="ASSET_MODIFIED",
                        asset_id=asset.id,
                        finding_id=None,
                        previous_state=json.dumps(old_baseline),
                        current_state=current_state_str,
                        actor_id=actor_id,
                    )
                    BaselineStateService.capture_asset_baseline(
                        asset.id, current_state_dict
                    )

            # 2. Risk score drift
            risk_score = AssetRiskSnapshotService.get_snapshot(asset.id).get(
                "risk_score", 0.0
            )
            old_risk = BaselineStateService.get_risk_baseline(asset.id)
            if old_risk is None:
                BaselineStateService.capture_risk_baseline(asset.id, risk_score)
            else:
                diff = risk_score - old_risk
                crossed_boundary = (old_risk < 75.0 <= risk_score) or (
                    risk_score < 75.0 <= old_risk
                )

                if diff >= 15.0 or (crossed_boundary and risk_score > old_risk):
                    await cls.emit_event(
                        db=db,
                        change_type="RISK_INCREASED",
                        asset_id=asset.id,
                        finding_id=None,
                        previous_state=str(old_risk),
                        current_state=str(risk_score),
                        actor_id=actor_id,
                    )
                    BaselineStateService.capture_risk_baseline(asset.id, risk_score)
                elif diff <= -15.0 or (crossed_boundary and risk_score < old_risk):
                    await cls.emit_event(
                        db=db,
                        change_type="RISK_DECREASED",
                        asset_id=asset.id,
                        finding_id=None,
                        previous_state=str(old_risk),
                        current_state=str(risk_score),
                        actor_id=actor_id,
                    )
                    BaselineStateService.capture_risk_baseline(asset.id, risk_score)

            # 3. Compliance & Governance drift
            gov_status = await GovernanceService.evaluate_asset_governance(db, asset.id)
            old_gov = BaselineStateService.get_governance_baseline(asset.id)
            if old_gov is None:
                BaselineStateService.capture_governance_baseline(
                    asset.id, gov_status.value
                )
            else:
                if (
                    old_gov == GovernanceStatus.COMPLIANT.value
                    and gov_status == GovernanceStatus.NON_COMPLIANT
                ):
                    # Check if risk acceptance expired
                    from src.services.risk_acceptance_service import (
                        RiskAcceptanceService,
                        RiskAcceptanceStatus,
                    )

                    acceptances = RiskAcceptanceService.get_acceptances_by_asset(
                        asset.id
                    )
                    has_expired = any(
                        a.status == RiskAcceptanceStatus.EXPIRED for a in acceptances
                    )
                    if has_expired:
                        await cls.emit_event(
                            db=db,
                            change_type="RISK_ACCEPTANCE_EXPIRED",
                            asset_id=asset.id,
                            finding_id=None,
                            previous_state=old_gov,
                            current_state=gov_status.value,
                            actor_id=actor_id,
                        )

                    await cls.emit_event(
                        db=db,
                        change_type="COMPLIANCE_FAILED",
                        asset_id=asset.id,
                        finding_id=None,
                        previous_state=old_gov,
                        current_state=gov_status.value,
                        actor_id=actor_id,
                    )
                    BaselineStateService.capture_governance_baseline(
                        asset.id, gov_status.value
                    )
                elif (
                    old_gov == GovernanceStatus.NON_COMPLIANT.value
                    and gov_status == GovernanceStatus.COMPLIANT
                ):
                    await cls.emit_event(
                        db=db,
                        change_type="COMPLIANCE_RESTORED",
                        asset_id=asset.id,
                        finding_id=None,
                        previous_state=old_gov,
                        current_state=gov_status.value,
                        actor_id=actor_id,
                    )
                    BaselineStateService.capture_governance_baseline(
                        asset.id, gov_status.value
                    )
                elif old_gov != gov_status.value:
                    await cls.emit_event(
                        db=db,
                        change_type="GOVERNANCE_DRIFT",
                        asset_id=asset.id,
                        finding_id=None,
                        previous_state=old_gov,
                        current_state=gov_status.value,
                        actor_id=actor_id,
                    )
                    BaselineStateService.capture_governance_baseline(
                        asset.id, gov_status.value
                    )

            # 4. Finding drift
            q_findings = select(Finding).where(
                Finding.asset_id == asset.id, Finding.status == "open"
            )
            res_findings = await db.execute(q_findings)
            findings = res_findings.scalars().all()

            for finding in findings:
                finding_state_dict = {
                    "title": finding.title,
                    "severity": finding.severity,
                    "status": finding.status,
                }
                finding_state_str = json.dumps(finding_state_dict)

                old_find_baseline = BaselineStateService.get_finding_baseline(
                    finding.id
                )
                if old_find_baseline is None:
                    # FINDING_ADDED
                    await cls.emit_event(
                        db=db,
                        change_type="FINDING_ADDED",
                        asset_id=asset.id,
                        finding_id=finding.id,
                        previous_state=None,
                        current_state=finding_state_str,
                        actor_id=actor_id,
                    )
                    BaselineStateService.capture_finding_baseline(
                        finding.id, finding_state_dict
                    )
                else:
                    if old_find_baseline.get("status") != "open":
                        # FINDING_REDISCOVERED
                        await cls.emit_event(
                            db=db,
                            change_type="FINDING_REDISCOVERED",
                            asset_id=asset.id,
                            finding_id=finding.id,
                            previous_state=json.dumps(old_find_baseline),
                            current_state=finding_state_str,
                            actor_id=actor_id,
                        )
                        BaselineStateService.capture_finding_baseline(
                            finding.id, finding_state_dict
                        )
                    elif (
                        old_find_baseline.get("severity") != finding.severity
                        or old_find_baseline.get("title") != finding.title
                    ):
                        # FINDING_MODIFIED
                        await cls.emit_event(
                            db=db,
                            change_type="FINDING_MODIFIED",
                            asset_id=asset.id,
                            finding_id=finding.id,
                            previous_state=json.dumps(old_find_baseline),
                            current_state=finding_state_str,
                            actor_id=actor_id,
                        )
                        BaselineStateService.capture_finding_baseline(
                            finding.id, finding_state_dict
                        )

            # Check resolved findings
            for fid, baseline_data in list(
                BaselineStateService._finding_baselines.items()
            ):
                f_obj = await db.get(Finding, fid)
                if f_obj and f_obj.asset_id == asset.id:
                    if baseline_data.get("status") == "open" and f_obj.status != "open":
                        resolved_state_dict = {
                            "title": f_obj.title,
                            "severity": f_obj.severity,
                            "status": f_obj.status,
                        }
                        await cls.emit_event(
                            db=db,
                            change_type="FINDING_RESOLVED",
                            asset_id=asset.id,
                            finding_id=fid,
                            previous_state=json.dumps(baseline_data),
                            current_state=json.dumps(resolved_state_dict),
                            actor_id=actor_id,
                        )
                        BaselineStateService.capture_finding_baseline(
                            fid, resolved_state_dict
                        )

        # Check removed assets
        for asset_id, baseline_data in list(
            BaselineStateService._asset_baselines.items()
        ):
            if asset_id not in active_asset_ids:
                # ASSET_REMOVED
                await cls.emit_event(
                    db=db,
                    change_type="ASSET_REMOVED",
                    asset_id=asset_id,
                    finding_id=None,
                    previous_state=json.dumps(baseline_data),
                    current_state=None,
                    actor_id=actor_id,
                )
                BaselineStateService._asset_baselines.pop(asset_id, None)

        # Trigger monitoring snapshot updates
        from src.services.monitoring_snapshot_service import (
            MonitoringSnapshotService,
        )

        await MonitoringSnapshotService.update_snapshot(db)
