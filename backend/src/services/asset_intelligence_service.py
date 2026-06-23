import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Asset, AssetPort, AssetService


class AssetIntelligenceService:
    """Service to aggregate asset intelligence including ports, services, technologies, and products."""

    # In-memory store for snapshots until a DB table is created in a future sprint
    _snapshots: Dict[uuid.UUID, Dict[str, Any]] = {}

    @classmethod
    async def generate_asset_snapshot(
        cls, db: AsyncSession, asset_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Generate an intelligence snapshot for a specific asset by aggregating port and service records."""

        # Query open ports
        q_ports = select(AssetPort).where(
            AssetPort.asset_id == asset_id, AssetPort.state == "open"
        )
        res_ports = await db.execute(q_ports)
        open_ports = res_ports.scalars().all()

        # Query services associated with all ports
        q_services = (
            select(AssetService).join(AssetPort).where(AssetPort.asset_id == asset_id)
        )
        res_services = await db.execute(q_services)
        services = res_services.scalars().all()

        technologies = set()
        products = set()

        for svc in services:
            if svc.product:
                technologies.add(svc.product)
                products.add(svc.product)

        snapshot = {
            "asset_id": str(asset_id),
            "open_port_count": len(open_ports),
            "service_count": len(services),
            "technology_stack": sorted(list(technologies)),
            "products": sorted(list(products)),
            "last_enriched_at": datetime.now(timezone.utc).isoformat(),
        }

        return snapshot

    @classmethod
    async def update_asset_snapshot(
        cls, db: AsyncSession, asset_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Recompute and save the snapshot for a specific asset."""
        snapshot = await cls.generate_asset_snapshot(db, asset_id)

        # Future-proof persistence design
        cls._snapshots[asset_id] = snapshot

        return snapshot

    @classmethod
    def get_asset_snapshot(cls, asset_id: uuid.UUID) -> Dict[str, Any]:
        """Retrieve the latest snapshot from storage."""
        return cls._snapshots.get(
            asset_id,
            {
                "asset_id": str(asset_id),
                "open_port_count": 0,
                "service_count": 0,
                "technology_stack": [],
                "products": [],
                "last_enriched_at": None,
            },
        )

    @classmethod
    async def update_asset_snapshot_for_scope(
        cls, db: AsyncSession, scope_id: uuid.UUID
    ) -> None:
        """Helper to recompute snapshots for all assets in a scope."""
        q_assets = select(Asset).where(
            Asset.scope_id == scope_id, Asset.deleted_at.is_(None)
        )
        res_assets = await db.execute(q_assets)
        assets = res_assets.scalars().all()

        for asset in assets:
            await cls.update_asset_snapshot(db, asset.id)
