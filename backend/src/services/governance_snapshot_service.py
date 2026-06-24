import uuid
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.services.governance_service import GovernanceService


class GovernanceSnapshotService:
    # in-memory store for platform governance snapshot
    _platform_snapshot: Optional[Dict[str, int]] = None
    # in-memory store for asset-specific governance status (optional cache optimization)
    _asset_statuses: Dict[uuid.UUID, str] = {}

    @classmethod
    async def get_snapshot(cls, db: AsyncSession) -> Dict[str, int]:
        """Get platform governance snapshot. Rebuilds if cache is empty."""
        if cls._platform_snapshot is None:
            await cls.update_snapshot(db)
        return cls._platform_snapshot or {
            "compliant_assets": 0,
            "non_compliant_assets": 0,
            "accepted_risks": 0,
            "expired_acceptances": 0,
            "exception_count": 0,
            "sla_breaches": 0,
        }

    @classmethod
    async def update_snapshot(
        cls, db: AsyncSession, asset_id: Optional[uuid.UUID] = None
    ) -> Dict[str, int]:
        """Rebuild and cache the governance snapshot."""
        # Note: If asset_id is provided, we can invalidate or re-evaluate.
        # Since it's a platform-wide snapshot, we recompute the whole state.
        summary = await GovernanceService.evaluate_platform_governance(db)
        cls._platform_snapshot = {
            "compliant_assets": summary["compliant_assets"],
            "non_compliant_assets": summary["non_compliant_assets"],
            "accepted_risks": summary["accepted_risks"],
            "expired_acceptances": summary["expired_acceptances"],
            "exception_count": summary["exception_count"],
            "sla_breaches": summary["sla_breaches"],
        }
        return cls._platform_snapshot

    @classmethod
    async def generate_snapshot(cls, db: AsyncSession) -> Dict[str, int]:
        """Generate and cache snapshot directly."""
        return await cls.update_snapshot(db)

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear all cached snapshots."""
        cls._platform_snapshot = None
        cls._asset_statuses.clear()
