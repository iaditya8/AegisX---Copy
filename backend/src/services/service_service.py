import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import (
    Asset,
    AssetHistory,
    AssetPort,
    AssetService,
    AuditLog,
    WorkflowEvent,
)


class ServiceService:
    """Service to handle persistence, history, events, and audits for Asset Services."""

    @staticmethod
    async def process_discovered_services(
        db: AsyncSession,
        scope_id: uuid.UUID,
        services_list: List[Dict[str, Any]],
        scan_run_id: uuid.UUID,
        workflow_id: uuid.UUID,
        actor_id: Optional[uuid.UUID],
    ) -> None:
        """Processes a list of normalized services."""
        now = datetime.now(timezone.utc)

        for svc_data in services_list:
            port_num = svc_data.get("port")
            protocol = svc_data.get("protocol", "tcp")
            service_name = svc_data.get("service", "unknown")
            product = svc_data.get("product")
            version = svc_data.get("version")
            banner = svc_data.get("banner")
            confidence = svc_data.get("confidence", 0.5)
            evidence = svc_data.get("evidence", {})
            addresses = svc_data.get("addresses", [])

            if not port_num or not addresses:
                continue

            # Need to find the associated asset port
            # Just grab the first asset in scope that matches one of the addresses
            asset = None
            for addr in addresses:
                q_asset = select(Asset).where(
                    Asset.scope_id == scope_id,
                    or_(Asset.host == addr, Asset.ip == addr),
                    Asset.deleted_at.is_(None),
                )
                res_asset = await db.execute(q_asset)
                asset = res_asset.scalar_one_or_none()
                if asset:
                    break

            if not asset:
                continue

            # Find the port
            q_port = select(AssetPort).where(
                AssetPort.asset_id == asset.id,
                AssetPort.port == port_num,
                AssetPort.protocol == protocol,
            )
            res_port = await db.execute(q_port)
            asset_port = res_port.scalar_one_or_none()
            if not asset_port:
                # Port must exist for service to be attached
                continue

            # Find existing service
            q_svc = select(AssetService).where(
                AssetService.asset_port_id == asset_port.id,
                AssetService.service_name == service_name,
            )
            res_svc = await db.execute(q_svc)
            existing_svc = res_svc.scalar_one_or_none()

            if not existing_svc:
                # Create
                new_svc = AssetService(
                    asset_port_id=asset_port.id,
                    service_name=service_name,
                    product=product,
                    version=version,
                    banner=banner,
                    confidence=confidence,
                    evidence=evidence,
                    first_seen=now,
                    last_seen=now,
                    created_at=now,
                    updated_at=now,
                )
                db.add(new_svc)
                await db.commit()
                await db.refresh(new_svc)

                # History
                history = AssetHistory(
                    asset_id=asset.id,
                    change_type="create",
                    entity_type="service",
                    old_value={},
                    new_value={"service_name": service_name, "version": version},
                    timestamp=now,
                    changed_by=actor_id,
                )
                db.add(history)

                # Audit
                audit = AuditLog(
                    action="create_service",
                    actor_id=actor_id,
                    target_id=new_svc.id,
                    target_type="service",
                    metadata_json={"service_name": service_name, "port": port_num},
                    timestamp=now,
                )
                db.add(audit)

                # Event
                event = WorkflowEvent(
                    workflow_id=workflow_id,
                    event_type="service.discovered",
                    correlation_id=scan_run_id,
                    payload={
                        "asset_service_id": str(new_svc.id),
                        "service_name": service_name,
                    },
                    timestamp=now,
                )
                db.add(event)
                await db.commit()

            else:
                # Update
                changed = False
                version_changed = False
                banner_changed = False
                old_version = existing_svc.version
                old_banner = existing_svc.banner

                if existing_svc.version != version:
                    existing_svc.version = version
                    changed = True
                    version_changed = True

                if existing_svc.banner != banner:
                    existing_svc.banner = banner
                    changed = True
                    banner_changed = True

                if existing_svc.product != product:
                    existing_svc.product = product
                    changed = True

                if existing_svc.confidence < confidence:
                    existing_svc.confidence = confidence
                    changed = True

                if existing_svc.evidence != evidence:
                    existing_svc.evidence = evidence
                    changed = True

                existing_svc.last_seen = now

                if changed:
                    existing_svc.updated_at = now

                    if version_changed:
                        history = AssetHistory(
                            asset_id=asset.id,
                            change_type="version_change",
                            entity_type="service",
                            old_value={"version": old_version},
                            new_value={"version": version},
                            timestamp=now,
                            changed_by=actor_id,
                        )
                        db.add(history)
                        event = WorkflowEvent(
                            workflow_id=workflow_id,
                            event_type="service.version_changed",
                            correlation_id=scan_run_id,
                            payload={
                                "asset_service_id": str(existing_svc.id),
                                "version": version,
                            },
                            timestamp=now,
                        )
                        db.add(event)

                    if banner_changed:
                        history = AssetHistory(
                            asset_id=asset.id,
                            change_type="banner_change",
                            entity_type="service",
                            old_value={"banner": old_banner},
                            new_value={"banner": banner},
                            timestamp=now,
                            changed_by=actor_id,
                        )
                        db.add(history)
                        event = WorkflowEvent(
                            workflow_id=workflow_id,
                            event_type="service.banner_changed",
                            correlation_id=scan_run_id,
                            payload={
                                "asset_service_id": str(existing_svc.id),
                                "banner": banner,
                            },
                            timestamp=now,
                        )
                        db.add(event)

                    if not version_changed and not banner_changed:
                        event = WorkflowEvent(
                            workflow_id=workflow_id,
                            event_type="service.updated",
                            correlation_id=scan_run_id,
                            payload={"asset_service_id": str(existing_svc.id)},
                            timestamp=now,
                        )
                        db.add(event)

                    audit = AuditLog(
                        action="update_service",
                        actor_id=actor_id,
                        target_id=existing_svc.id,
                        target_type="service",
                        metadata_json={"service_name": service_name},
                        timestamp=now,
                    )
                    db.add(audit)

                await db.commit()

        # Recompute Asset Intelligence Snapshot
        from src.services.asset_intelligence_service import AssetIntelligenceService

        await AssetIntelligenceService.update_asset_snapshot_for_scope(db, scope_id)
