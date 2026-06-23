import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import (
    Asset,
    AuditLog,
    Finding,
    FindingHistory,
    WorkflowEvent,
)
from src.services.finding_snapshot_service import FindingSnapshotService


class FindingReconciliationService:
    """Service to reconcile findings at the end of a scan, marking missing findings."""

    @staticmethod
    def _matches_templates(template_id: str, configured_templates: List[str]) -> bool:
        """Helper to check if a template ID matches any configured templates in scan."""
        if not configured_templates:
            return True
        for ct in configured_templates:
            ct_clean = ct.strip().lower()
            t_clean = template_id.strip().lower()
            if ct_clean in t_clean or t_clean.startswith(ct_clean):
                return True
        return False

    @classmethod
    async def reconcile_findings(
        cls,
        db: AsyncSession,
        scope_id: uuid.UUID,
        scan_run_id: uuid.UUID,
        workflow_id: uuid.UUID,
        actor_id: Optional[uuid.UUID],
        source_plugin: str,
        step_type: str,
        step_config: Dict[str, Any],
        processed_fingerprints: List[str],
    ) -> None:
        """Identify findings that disappeared in the current scan run and mark them."""
        now = datetime.now(timezone.utc)

        # 1. Retrieve assets belonging to the scope
        q_assets = select(Asset.id).where(
            Asset.scope_id == scope_id, Asset.deleted_at.is_(None)
        )
        res_assets = await db.execute(q_assets)
        asset_ids = res_assets.scalars().all()
        if not asset_ids:
            return

        # 2. Retrieve findings in the scope for the same plugin (scanner class)
        # We only reconcile findings that are currently active (open/acknowledged)
        # and not already marked closed_by_scan.
        q_findings = select(Finding).where(
            Finding.asset_id.in_(asset_ids),
            Finding.source_plugin == source_plugin,
            Finding.status.in_(["open", "acknowledged"]),
        )
        res_findings = await db.execute(q_findings)
        findings = res_findings.scalars().all()

        # Get configured templates from step config
        configured_templates = step_config.get("templates", [])
        if isinstance(configured_templates, str):
            configured_templates = [configured_templates]

        for finding in findings:
            meta = dict(finding.metadata_json or {})
            if meta.get("closed_by_scan", False):
                continue

            # Check if this finding falls under the templates configured for the scan
            if not cls._matches_templates(finding.template_id, configured_templates):
                continue

            # If it was NOT returned/processed by the current scan run
            if finding.fingerprint not in processed_fingerprints:
                # Mark as closed by scan and missing
                meta["closed_by_scan"] = True
                meta["last_scan_missing"] = True
                finding.metadata_json = meta
                finding.updated_at = now

                # Do not transition finding status. Status remains unchanged.

                # Generate FindingHistory
                history = FindingHistory(
                    finding_id=finding.id,
                    change_type="metadata_change",
                    old_value={"closed_by_scan": False, "last_scan_missing": False},
                    new_value={"closed_by_scan": True, "last_scan_missing": True},
                    changed_by=actor_id,
                    created_at=now,
                )
                db.add(history)

                # Generate AuditLog
                audit = AuditLog(
                    actor_id=actor_id,
                    action="closed_by_scan",
                    target_type="finding",
                    target_id=finding.id,
                    metadata_json={
                        "template_id": finding.template_id,
                        "closed_by_scan": True,
                        "last_scan_missing": True,
                    },
                    timestamp=now,
                )
                db.add(audit)

                # Generate finding.no_longer_detected event
                event_id = uuid.uuid4()
                event = WorkflowEvent(
                    id=event_id,
                    workflow_id=workflow_id,
                    event_type="finding.no_longer_detected",
                    correlation_id=scan_run_id,
                    payload={
                        "event_id": str(event_id),
                        "correlation_id": str(scan_run_id),
                        "workflow_id": str(workflow_id),
                        "scan_run_id": str(scan_run_id),
                        "timestamp": now.isoformat(),
                        "finding_id": str(finding.id),
                        "asset_id": str(finding.asset_id),
                        "template_id": finding.template_id,
                        "severity": finding.severity,
                    },
                    timestamp=now,
                )
                db.add(event)

                # Update the asset's snapshot
                await FindingSnapshotService.update_finding_snapshot(
                    db, finding.asset_id
                )
                from src.services.report_cache_service import ReportCacheService

                ReportCacheService.invalidate_for_asset(finding.asset_id)

        await db.commit()
