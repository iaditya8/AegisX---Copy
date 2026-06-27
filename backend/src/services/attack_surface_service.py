import uuid
from typing import Set, Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models import AssetPort
from src.services.attack_surface_registry import AttackSurfaceRegistry


class AttackSurfaceService:
    # Class mapping of ports to attack surface categories
    PORT_MAPPINGS = {
        80: "WEB_APPLICATION",
        443: "WEB_APPLICATION",
        8080: "API",
        8443: "API",
        8000: "API",
        5000: "API",
        22: "HOST",
        3389: "HOST",
        25: "EMAIL",
        110: "EMAIL",
        143: "EMAIL",
        993: "EMAIL",
        995: "EMAIL",
        587: "EMAIL",
        53: "IDENTITY",
        389: "IDENTITY",
        636: "IDENTITY",
        21: "NETWORK_SERVICE",
        445: "NETWORK_SERVICE",
        139: "NETWORK_SERVICE",
        1433: "NETWORK_SERVICE",
        3306: "NETWORK_SERVICE",
        5432: "NETWORK_SERVICE",
        27017: "NETWORK_SERVICE",
        6379: "NETWORK_SERVICE",
    }

    @classmethod
    async def get_asset_categories(cls, db: AsyncSession, asset_id: uuid.UUID) -> Set[str]:
        """Automatically classify an asset's attack surface categories based on its open ports/services."""
        q_ports = select(AssetPort).where(
            AssetPort.asset_id == asset_id, AssetPort.state == "open"
        )
        res = await db.execute(q_ports)
        open_ports = res.scalars().all()

        categories = set()
        for p in open_ports:
            cat = cls.PORT_MAPPINGS.get(p.port)
            if cat and AttackSurfaceRegistry.is_valid_category(cat):
                categories.add(cat)

        # Fallback to HOST if there are no specific open ports mapped but we know it exists
        if not categories:
            categories.add("HOST")

        return categories
