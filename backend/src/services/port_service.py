import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import (
    Asset,
    AssetHistory,
    AssetPort,
    AuditLog,
    WorkflowEvent,
)


class PortService:
    """Service to handle persistence, history, events, and audits for Asset Ports."""

    @staticmethod
    async def process_discovered_ports(
        db: AsyncSession,
        scope_id: uuid.UUID,
        ports_list: List[Dict[str, Any]],
        scan_run_id: uuid.UUID,
        workflow_id: uuid.UUID,
        actor_id: Optional[uuid.UUID],
    ) -> None:
        """Processes a list of normalized ports."""
        now = datetime.now(timezone.utc)

        for port_data in ports_list:
            host_or_ip = port_data.get("host_or_ip")
            port_num = port_data.get("port")
            protocol = port_data.get("protocol", "tcp")
            state = port_data.get("state", "unknown")
            evidence = port_data.get("evidence", {})

            if not host_or_ip or not port_num:
                continue

            # Find matching asset in scope
            q_asset = select(Asset).where(
                Asset.scope_id == scope_id,
                or_(Asset.host == host_or_ip, Asset.ip == host_or_ip),
                Asset.deleted_at.is_(None),
            )
            res_asset = await db.execute(q_asset)
            asset = res_asset.scalar_one_or_none()
            if not asset:
                continue  # Asset must exist first

            # Find existing port
            q_port = select(AssetPort).where(
                AssetPort.asset_id == asset.id,
                AssetPort.port == port_num,
                AssetPort.protocol == protocol,
            )
            res_port = await db.execute(q_port)
            existing_port = res_port.scalar_one_or_none()

            if not existing_port:
                # Create
                new_port = AssetPort(
                    asset_id=asset.id,
                    port=port_num,
                    protocol=protocol,
                    state=state,
                    evidence=evidence,
                    first_seen=now,
                    last_seen=now,
                    created_at=now,
                    updated_at=now,
                )
                db.add(new_port)
                await db.commit()
                await db.refresh(new_port)

                # History
                history = AssetHistory(
                    asset_id=asset.id,
                    change_type="create",
                    entity_type="port",
                    old_value={},
                    new_value={"state": state, "port": port_num, "protocol": protocol},
                    timestamp=now,
                    changed_by=actor_id,
                )
                db.add(history)

                # Audit
                audit = AuditLog(
                    action="create_port",
                    actor_id=actor_id,
                    target_id=new_port.id,
                    target_type="port",
                    metadata_json={
                        "port": port_num,
                        "protocol": protocol,
                        "state": state,
                    },
                    timestamp=now,
                )
                db.add(audit)

                # Event
                event = WorkflowEvent(
                    workflow_id=workflow_id,
                    event_type="port.discovered",
                    correlation_id=scan_run_id,
                    payload={"asset_port_id": str(new_port.id), "port": port_num},
                    timestamp=now,
                )
                db.add(event)
                await db.commit()

            else:
                # Update
                changed = False
                state_changed = False
                old_state = existing_port.state

                if existing_port.state != state:
                    existing_port.state = state
                    changed = True
                    state_changed = True

                if existing_port.evidence != evidence:
                    existing_port.evidence = evidence
                    changed = True

                existing_port.last_seen = now

                if changed:
                    existing_port.updated_at = now

                    if state_changed:
                        # History for state transition
                        history = AssetHistory(
                            asset_id=asset.id,
                            change_type="state_change",
                            entity_type="port",
                            old_value={"state": old_state},
                            new_value={"state": state},
                            timestamp=now,
                            changed_by=actor_id,
                        )
                        db.add(history)

                        # Audit for state transition
                        audit = AuditLog(
                            action="update_port_state",
                            actor_id=actor_id,
                            target_id=existing_port.id,
                            target_type="port",
                            metadata_json={"old_state": old_state, "new_state": state},
                            timestamp=now,
                        )
                        db.add(audit)

                    # Event
                    event = WorkflowEvent(
                        workflow_id=workflow_id,
                        event_type="port.updated",
                        correlation_id=scan_run_id,
                        payload={
                            "asset_port_id": str(existing_port.id),
                            "state": state,
                        },
                        timestamp=now,
                    )
                    db.add(event)

                await db.commit()

        # Recompute Asset Intelligence Snapshot
        from src.services.asset_intelligence_service import AssetIntelligenceService

        await AssetIntelligenceService.update_asset_snapshot_for_scope(db, scope_id)
