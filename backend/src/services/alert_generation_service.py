import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.alert import AlertStatus, AlertType
from src.services.alert_fingerprint_service import AlertFingerprintService
from src.services.alert_lifecycle_service import (
    AlertLifecycleService,
    AlertRecord,
)
from src.services.alert_severity_registry import AlertSeverityRegistry
from src.services.audit_service import create_audit_entry
from src.services.workflow_event_service import WorkflowEventService


class AlertGenerationService:
    @classmethod
    async def generate_alerts(cls, db: AsyncSession) -> None:
        """Consume monitoring logs and generate deduplicated operational alerts."""
        from src.services.continuous_refresh_service import (
            ContinuousRefreshService,
        )
        from src.services.remediation_aging_service import (
            RemediationAgingService,
        )

        events = ContinuousRefreshService.get_all_events()

        # 1. Map and generate alerts from monitoring events
        for event in events:
            alert_type = None
            title = ""
            description = ""
            finding_id = event.finding_id
            remediation_id = None
            recommendation_id = None

            change_type = event.change_type
            if change_type in ["ASSET_ADDED", "ASSET_MODIFIED", "ASSET_REMOVED"]:
                alert_type = AlertType.ASSET_DRIFT
                title = f"Asset Drift: {change_type} on asset {event.asset_id}"
                description = (
                    f"Asset drift event of type {change_type} was detected. "
                    f"Previous state: {event.previous_state}, "
                    f"current state: {event.current_state}"
                )

            elif change_type in ["FINDING_ADDED", "FINDING_REDISCOVERED"]:
                is_critical = False
                if event.current_state:
                    try:
                        state_dict = json.loads(event.current_state)
                        if state_dict.get("severity") == "critical":
                            is_critical = True
                    except Exception:
                        pass

                if is_critical:
                    alert_type = AlertType.CRITICAL_FINDING
                    title = (
                        f"Critical Finding: {change_type} on asset " f"{event.asset_id}"
                    )
                else:
                    alert_type = AlertType.FINDING_DRIFT
                    title = (
                        f"Finding Drift: {change_type} on asset " f"{event.asset_id}"
                    )

                description = (
                    f"Finding drift event of type {change_type} was detected. "
                    f"Previous state: {event.previous_state}, "
                    f"current state: {event.current_state}"
                )

            elif change_type == "FINDING_RESOLVED":
                alert_type = AlertType.FINDING_DRIFT
                title = f"Finding Drift: FINDING_RESOLVED on asset " f"{event.asset_id}"
                description = (
                    f"Finding was resolved. Previous state: {event.previous_state}, "
                    f"current state: {event.current_state}"
                )

            elif change_type in ["RISK_INCREASED", "RISK_DECREASED"]:
                alert_type = AlertType.RISK_DRIFT
                title = f"Risk Drift: {change_type} on asset {event.asset_id}"
                description = (
                    f"Risk score drift detected. Previous state: {event.previous_state}, "
                    f"current state: {event.current_state}"
                )

            elif change_type == "RISK_ACCEPTANCE_EXPIRED":
                alert_type = AlertType.RISK_ACCEPTANCE_EXPIRATION
                title = f"Risk Acceptance Expired on asset {event.asset_id}"
                description = (
                    f"Risk acceptance has expired. Previous state: {event.previous_state}, "
                    f"current state: {event.current_state}"
                )

            elif change_type in [
                "COMPLIANCE_FAILED",
                "COMPLIANCE_RESTORED",
                "GOVERNANCE_DRIFT",
            ]:
                alert_type = AlertType.COMPLIANCE_DRIFT
                title = f"Compliance Drift: {change_type} on asset {event.asset_id}"
                description = (
                    f"Compliance posture drift detected. Previous state: {event.previous_state}, "
                    f"current state: {event.current_state}"
                )

            if alert_type:
                fingerprint = AlertFingerprintService.calculate_fingerprint(
                    alert_type=alert_type,
                    asset_id=event.asset_id,
                    finding_id=finding_id,
                    recommendation_id=recommendation_id,
                    remediation_id=remediation_id,
                )
                existing = AlertLifecycleService.get_alert_by_fingerprint(fingerprint)
                if not existing:
                    alert_id = uuid.uuid4()
                    severity = AlertSeverityRegistry.get_severity(alert_type)
                    new_alert = AlertRecord(
                        alert_id=alert_id,
                        alert_fingerprint=fingerprint,
                        alert_type=alert_type,
                        severity=severity,
                        status=AlertStatus.OPEN,
                        title=title,
                        description=description,
                        asset_id=event.asset_id,
                        finding_id=finding_id,
                        recommendation_id=recommendation_id,
                        remediation_id=remediation_id,
                    )

                    AlertLifecycleService._alerts[alert_id] = new_alert
                    AlertLifecycleService._fingerprint_lookup[fingerprint] = alert_id

                    # Emit workflow event
                    await WorkflowEventService.emit_event(
                        db=db,
                        event_type="alert.created",
                        payload={
                            "alert_id": str(alert_id),
                            "alert_type": alert_type.value,
                        },
                    )

                    # Log audit entry
                    await create_audit_entry(
                        db=db,
                        actor_id=None,
                        action="alert.created",
                        target_type="alert",
                        target_id=alert_id,
                        metadata={"alert_type": alert_type.value},
                    )

        # 2. SLA Breach auto-alerts
        overdue_remediations = RemediationAgingService.get_overdue_items()
        overdue_ids = {r.remediation_id for r in overdue_remediations}

        for r in overdue_remediations:
            fingerprint = AlertFingerprintService.calculate_fingerprint(
                alert_type=AlertType.SLA_BREACH,
                asset_id=r.asset_id,
                finding_id=r.finding_id,
                remediation_id=r.remediation_id,
            )
            existing = AlertLifecycleService.get_alert_by_fingerprint(fingerprint)
            if not existing:
                alert_id = uuid.uuid4()
                severity = AlertSeverityRegistry.get_severity(AlertType.SLA_BREACH)
                new_alert = AlertRecord(
                    alert_id=alert_id,
                    alert_fingerprint=fingerprint,
                    alert_type=AlertType.SLA_BREACH,
                    severity=severity,
                    status=AlertStatus.OPEN,
                    title=f"SLA Breach for remediation {r.remediation_id}",
                    description=(
                        f"Remediation {r.remediation_id} has breached its SLA. "
                        f"Status: {r.status.value}, due date: {r.due_date}"
                    ),
                    asset_id=r.asset_id,
                    finding_id=r.finding_id,
                    remediation_id=r.remediation_id,
                )

                AlertLifecycleService._alerts[alert_id] = new_alert
                AlertLifecycleService._fingerprint_lookup[fingerprint] = alert_id

                # Emit workflow event
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="alert.created",
                    payload={
                        "alert_id": str(alert_id),
                        "alert_type": AlertType.SLA_BREACH.value,
                    },
                )

                # Log audit entry
                await create_audit_entry(
                    db=db,
                    actor_id=None,
                    action="alert.created",
                    target_type="alert",
                    target_id=alert_id,
                    metadata={"alert_type": AlertType.SLA_BREACH.value},
                )

        # 3. Backend Auto-Resolving
        # a) Resolve alerts if finding is resolved
        for event in events:
            if event.change_type == "FINDING_RESOLVED":
                for alert in AlertLifecycleService.get_all_alerts():
                    if alert.finding_id == event.finding_id and alert.status not in [
                        AlertStatus.RESOLVED,
                        AlertStatus.SUPPRESSED,
                    ]:
                        await AlertLifecycleService.transition_alert(
                            db, alert.alert_id, AlertStatus.RESOLVED
                        )

            # b) Resolve compliance drift if compliance restored
            elif event.change_type == "COMPLIANCE_RESTORED":
                for alert in AlertLifecycleService.get_all_alerts():
                    if (
                        alert.asset_id == event.asset_id
                        and alert.alert_type == AlertType.COMPLIANCE_DRIFT
                        and alert.status
                        not in [AlertStatus.RESOLVED, AlertStatus.SUPPRESSED]
                    ):
                        await AlertLifecycleService.transition_alert(
                            db, alert.alert_id, AlertStatus.RESOLVED
                        )

        # c) Resolve SLA breach alerts if remediation is no longer overdue
        for alert in AlertLifecycleService.get_all_alerts():
            if alert.alert_type == AlertType.SLA_BREACH and alert.status not in [
                AlertStatus.RESOLVED,
                AlertStatus.SUPPRESSED,
            ]:
                if alert.remediation_id not in overdue_ids:
                    await AlertLifecycleService.transition_alert(
                        db, alert.alert_id, AlertStatus.RESOLVED
                    )

        from src.services.alert_snapshot_service import AlertSnapshotService

        AlertSnapshotService.invalidate_cache()
