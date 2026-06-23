import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import (
    Asset,
    AssetPort,
    AssetService,
    AuditLog,
    Finding,
    FindingHistory,
    WorkflowEvent,
)
from src.services.finding_evidence_service import FindingEvidenceService
from src.services.finding_fingerprint_service import FindingFingerprintService
from src.services.finding_snapshot_service import FindingSnapshotService


def clean_host(host_str: str) -> str:
    """Extract host/IP from raw target string or URL."""
    if not host_str:
        return ""
    if "://" in host_str:
        try:
            parsed = urlparse(host_str)
            host_str = parsed.hostname or host_str
        except Exception:
            pass
    if ":" in host_str:
        host_str = host_str.split(":")[0]
    return host_str


class FindingService:
    """Service to handle findings lifecycle, history, events, and audits."""

    @classmethod
    async def process_discovered_findings(
        cls,
        db: AsyncSession,
        scope_id: uuid.UUID,
        findings_list: List[Dict[str, Any]],
        scan_run_id: uuid.UUID,
        workflow_id: uuid.UUID,
        actor_id: Optional[uuid.UUID],
    ) -> List[str]:
        """Process a list of normalized findings discovered during scanning."""
        now = datetime.now(timezone.utc)
        processed_fingerprints: List[str] = []

        for entry in findings_list:
            f_data = entry["finding"]
            e_data = entry["evidence"]

            # Resolve target asset in scope
            host_raw = e_data.get("metadata_json", {}).get("host", "")
            host_clean = clean_host(host_raw)

            q_asset = select(Asset).where(
                Asset.scope_id == scope_id,
                or_(Asset.host == host_clean, Asset.ip == host_clean),
                Asset.deleted_at.is_(None),
            )
            res_asset = await db.execute(q_asset)
            asset = res_asset.scalar_one_or_none()
            if not asset:
                continue

            # Identify port/service
            port_num = None
            if "://" in host_raw:
                try:
                    parsed = urlparse(host_raw)
                    port_num = parsed.port
                    if not port_num:
                        port_num = 443 if parsed.scheme == "https" else 80
                except Exception:
                    pass
            elif ":" in host_raw:
                try:
                    port_num = int(host_raw.split(":")[-1])
                except ValueError:
                    pass

            port_id = None
            service_id = None
            if port_num is not None:
                q_port = select(AssetPort).where(
                    AssetPort.asset_id == asset.id,
                    AssetPort.port == port_num,
                )
                res_port = await db.execute(q_port)
                asset_port = res_port.scalar_one_or_none()
                if asset_port:
                    port_id = asset_port.id
                    q_svc = select(AssetService).where(
                        AssetService.asset_port_id == port_id
                    )
                    res_svc = await db.execute(q_svc)
                    asset_service = res_svc.scalar_one_or_none()
                    if asset_service:
                        service_id = asset_service.id

            # Generate fingerprint
            matched_at = e_data.get("matched_at") or ""
            matched_host = None
            matched_path = None
            if matched_at:
                try:
                    parsed = urlparse(matched_at)
                    matched_host = parsed.netloc
                    matched_path = parsed.path
                except Exception:
                    pass

            template_id = f_data["template_id"]
            fingerprint = FindingFingerprintService.generate_fingerprint(
                asset.id, template_id, matched_host, matched_path
            )
            processed_fingerprints.append(fingerprint)

            # Check if exists
            q_find = select(Finding).where(Finding.fingerprint == fingerprint)
            res_find = await db.execute(q_find)
            finding = res_find.scalar_one_or_none()

            if not finding:
                # 1. Create finding
                finding = Finding(
                    asset_id=asset.id,
                    asset_port_id=port_id,
                    asset_service_id=service_id,
                    title=f_data["title"],
                    description=f_data["description"],
                    severity=f_data["severity"],
                    status="open",
                    template_id=template_id,
                    template_name=f_data["template_name"],
                    source_plugin=f_data["source_plugin"],
                    first_seen=now,
                    last_seen=now,
                    created_at=now,
                    updated_at=now,
                    fingerprint=fingerprint,
                    metadata_json={
                        "cves": [],
                        "cvss": None,
                        "epss": None,
                        "closed_by_scan": False,
                        "last_scan_missing": False,
                        "last_detected_scan_run_id": (
                            str(scan_run_id) if scan_run_id else None
                        ),
                    },
                )
                db.add(finding)
                await db.commit()
                await db.refresh(finding)

                # 2. History
                history = FindingHistory(
                    finding_id=finding.id,
                    change_type="create",
                    new_value={"status": "open", "severity": finding.severity},
                    changed_by=actor_id,
                    created_at=now,
                )
                db.add(history)

                # 3. Audit
                audit = AuditLog(
                    actor_id=actor_id,
                    action="create_finding",
                    target_type="finding",
                    target_id=finding.id,
                    metadata_json={
                        "template_id": template_id,
                        "severity": finding.severity,
                    },
                    timestamp=now,
                )
                db.add(audit)

                # 4. Event
                event_id = uuid.uuid4()
                event = WorkflowEvent(
                    id=event_id,
                    workflow_id=workflow_id,
                    event_type="finding.discovered",
                    correlation_id=scan_run_id,
                    payload={
                        "event_id": str(event_id),
                        "correlation_id": str(scan_run_id),
                        "workflow_id": str(workflow_id),
                        "scan_run_id": str(scan_run_id),
                        "timestamp": now.isoformat(),
                        "finding_id": str(finding.id),
                        "asset_id": str(asset.id),
                        "template_id": template_id,
                        "severity": finding.severity,
                    },
                    timestamp=now,
                )
                db.add(event)
                await db.commit()

            else:
                # Existing finding - update last_seen
                old_status = finding.status
                old_severity = finding.severity

                finding.last_seen = now
                finding.updated_at = now

                meta = dict(finding.metadata_json or {})
                meta["last_detected_scan_run_id"] = (
                    str(scan_run_id) if scan_run_id else None
                )

                # Rediscovery of scan-closed finding
                if meta.get("closed_by_scan", False):
                    meta["closed_by_scan"] = False
                    meta["last_scan_missing"] = False

                    # Emit finding.reopened event (rediscovery resets closure)
                    event_id = uuid.uuid4()
                    event = WorkflowEvent(
                        id=event_id,
                        workflow_id=workflow_id,
                        event_type="finding.reopened",
                        correlation_id=scan_run_id,
                        payload={
                            "event_id": str(event_id),
                            "correlation_id": str(scan_run_id),
                            "workflow_id": str(workflow_id),
                            "scan_run_id": str(scan_run_id),
                            "timestamp": now.isoformat(),
                            "finding_id": str(finding.id),
                            "asset_id": str(asset.id),
                            "template_id": template_id,
                            "severity": finding.severity,
                        },
                        timestamp=now,
                    )
                    db.add(event)

                    # Create metadata_change history record
                    history = FindingHistory(
                        finding_id=finding.id,
                        change_type="metadata_change",
                        old_value={"closed_by_scan": True, "last_scan_missing": True},
                        new_value={"closed_by_scan": False, "last_scan_missing": False},
                        changed_by=actor_id,
                        created_at=now,
                    )
                    db.add(history)

                finding.metadata_json = meta

                # Change 6: Reopen resolved finding
                if old_status == "resolved":
                    finding.status = "open"

                    # Reopened event
                    event_id = uuid.uuid4()
                    event = WorkflowEvent(
                        id=event_id,
                        workflow_id=workflow_id,
                        event_type="finding.reopened",
                        correlation_id=scan_run_id,
                        payload={
                            "event_id": str(event_id),
                            "correlation_id": str(scan_run_id),
                            "workflow_id": str(workflow_id),
                            "scan_run_id": str(scan_run_id),
                            "timestamp": now.isoformat(),
                            "finding_id": str(finding.id),
                            "asset_id": str(asset.id),
                            "template_id": template_id,
                            "severity": finding.severity,
                        },
                        timestamp=now,
                    )
                    db.add(event)

                    # Reopened history
                    history = FindingHistory(
                        finding_id=finding.id,
                        change_type="status_change",
                        old_value={"status": "resolved"},
                        new_value={"status": "open"},
                        changed_by=actor_id,
                        created_at=now,
                    )
                    db.add(history)

                    # Reopened audit
                    audit = AuditLog(
                        actor_id=actor_id,
                        action="reopen_finding",
                        target_type="finding",
                        target_id=finding.id,
                        metadata_json={
                            "template_id": template_id,
                            "old_status": "resolved",
                            "new_status": "open",
                        },
                        timestamp=now,
                    )
                    db.add(audit)

                # Severity updates
                if old_severity != f_data["severity"]:
                    finding.severity = f_data["severity"]

                    # Updated event
                    event_id = uuid.uuid4()
                    event = WorkflowEvent(
                        id=event_id,
                        workflow_id=workflow_id,
                        event_type="finding.updated",
                        correlation_id=scan_run_id,
                        payload={
                            "event_id": str(event_id),
                            "correlation_id": str(scan_run_id),
                            "workflow_id": str(workflow_id),
                            "scan_run_id": str(scan_run_id),
                            "timestamp": now.isoformat(),
                            "finding_id": str(finding.id),
                            "asset_id": str(asset.id),
                            "template_id": template_id,
                            "severity": finding.severity,
                        },
                        timestamp=now,
                    )
                    db.add(event)

                    # Updated history
                    history = FindingHistory(
                        finding_id=finding.id,
                        change_type="severity_change",
                        old_value={"severity": old_severity},
                        new_value={"severity": finding.severity},
                        changed_by=actor_id,
                        created_at=now,
                    )
                    db.add(history)

                    # Updated audit
                    audit = AuditLog(
                        actor_id=actor_id,
                        action="update_finding",
                        target_type="finding",
                        target_id=finding.id,
                        metadata_json={
                            "template_id": template_id,
                            "old_severity": old_severity,
                            "new_severity": finding.severity,
                        },
                        timestamp=now,
                    )
                    db.add(audit)

                # Save updates
                await db.commit()

            # 7. Create/version evidence
            await FindingEvidenceService.create_evidence(
                db=db,
                finding_id=finding.id,
                evidence_type=e_data["evidence_type"],
                raw_request=e_data["raw_request"],
                raw_response=e_data["raw_response"],
                matched_at=e_data["matched_at"],
                matcher_name=e_data["matcher_name"],
                matcher_value=e_data["matcher_value"],
                metadata_json=e_data["metadata_json"],
            )

            # Recompute snapshot on creation/reopen/severity change
            await FindingSnapshotService.update_finding_snapshot(db, asset.id)
            from src.services.recommendation_snapshot_service import (
                RecommendationSnapshotService,
            )

            await RecommendationSnapshotService.update_snapshot(db, asset.id)
            from src.services.report_cache_service import ReportCacheService

            ReportCacheService.invalidate_for_asset(asset.id)

        return processed_fingerprints

    @classmethod
    async def update_status(
        cls,
        db: AsyncSession,
        finding_id: uuid.UUID,
        new_status: str,
        actor_id: Optional[uuid.UUID],
    ) -> Finding:
        """Manually transition a finding's lifecycle status."""
        finding = await db.get(Finding, finding_id)
        if not finding:
            raise ValueError("Finding not found")

        old_status = finding.status
        if old_status == new_status:
            return finding

        finding.status = new_status
        finding.updated_at = datetime.now(timezone.utc)

        # Map transition action to audit action
        audit_actions = {
            "acknowledged": "acknowledged_finding",
            "resolved": "resolve_finding",
            "suppressed": "suppress_finding",
            "open": "reopen_finding",
        }
        action = audit_actions.get(new_status, "update_finding")

        # Map transition action to event type
        event_types = {
            "acknowledged": "finding.updated",
            "resolved": "finding.resolved",
            "suppressed": "finding.suppressed",
            "open": "finding.reopened",
        }
        event_type = event_types.get(new_status, "finding.updated")

        now = datetime.now(timezone.utc)

        # History
        history = FindingHistory(
            finding_id=finding.id,
            change_type="status_change",
            old_value={"status": old_status},
            new_value={"status": new_status},
            changed_by=actor_id,
            created_at=now,
        )
        db.add(history)

        # Audit
        audit = AuditLog(
            actor_id=actor_id,
            action=action,
            target_type="finding",
            target_id=finding.id,
            metadata_json={
                "template_id": finding.template_id,
                "old_status": old_status,
                "new_status": new_status,
            },
            timestamp=now,
        )
        db.add(audit)

        # Event
        event_id = uuid.uuid4()
        event = WorkflowEvent(
            id=event_id,
            workflow_id=uuid.uuid4(),  # Mock or use default
            event_type=event_type,
            correlation_id=None,
            payload={
                "event_id": str(event_id),
                "correlation_id": None,
                "workflow_id": None,
                "scan_run_id": None,
                "timestamp": now.isoformat(),
                "finding_id": str(finding.id),
                "asset_id": str(finding.asset_id),
                "template_id": finding.template_id,
                "severity": finding.severity,
                "old_status": old_status,
                "new_status": new_status,
            },
            timestamp=now,
        )
        db.add(event)

        await db.commit()

        # Recompute snapshot
        await FindingSnapshotService.update_finding_snapshot(db, finding.asset_id)
        from src.services.recommendation_snapshot_service import (
            RecommendationSnapshotService,
        )

        await RecommendationSnapshotService.update_snapshot(db, finding.asset_id)
        from src.services.report_cache_service import ReportCacheService

        ReportCacheService.invalidate_for_asset(finding.asset_id)

        return finding

        ReportCacheService.invalidate_for_asset(finding.asset_id)

        return finding
