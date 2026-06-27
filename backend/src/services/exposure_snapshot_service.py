import uuid
from typing import Dict, Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models import Asset
from src.domain.entities.exposure import ExposureStatus, ExposureSeverity
from src.services.exposure_service import ExposureService
from src.services.attack_surface_service import AttackSurfaceService


class ExposureSnapshotService:
    # Cache store: scope_id (None for global) -> Snapshot dictionary
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear the snapshot cache."""
        cls._snapshots.clear()

    @classmethod
    def get_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Get the cached snapshot, generating a minimal default if cache is missing or corrupted."""
        snap = cls._snapshots.get(scope_id)
        if not snap or not isinstance(snap, dict) or "summary" not in snap:
            # Minimal fallback to avoid crashes
            return {
                "summary": {
                    "total_exposures": 0,
                    "open_count": 0,
                    "critical_count": 0,
                    "organization_risk_score": 0.0,
                    "attack_surface_coverage": 100.0,
                },
                "status_counts": {},
                "exposures": {},
                "attack_surface": {},
            }
        return snap

    @classmethod
    async def generate_snapshot(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None
    ) -> dict:
        """Dynamically rebuild the exposure snapshot statistics from scratch and update cache."""
        # 1. Fetch assets
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        if scope_id:
            q_assets = q_assets.where(Asset.scope_id == scope_id)
        assets = (await db.execute(q_assets)).scalars().all()
        asset_ids = {a.id for a in assets}

        # 2. Fetch current exposures
        all_exposures = ExposureService.get_all_exposures()
        if scope_id:
            all_exposures = [e for e in all_exposures if e.asset_id in asset_ids]

        # 3. Calculate status and severity counts
        total_exposures = len(all_exposures)
        open_count = sum(1 for e in all_exposures if e.status == ExposureStatus.OPEN)
        critical_count = sum(1 for e in all_exposures if e.severity == ExposureSeverity.CRITICAL)

        status_counts = {}
        for e in all_exposures:
            status_counts[e.status.value] = status_counts.get(e.status.value, 0) + 1

        # 4. Calculate organization risk score
        open_exposures = [e for e in all_exposures if e.status == ExposureStatus.OPEN]
        if open_exposures:
            org_risk_score = round(sum(e.risk_score for e in open_exposures) / len(open_exposures), 2)
        else:
            org_risk_score = 0.0

        # 5. Classify attack surface categories and calculate coverage
        attack_surface_map = {}
        assets_with_exposure = set()
        for asset in assets:
            cats = await AttackSurfaceService.get_asset_categories(db, asset.id)
            attack_surface_map[str(asset.id)] = sorted(list(cats))

            # check if asset has exposures
            if any(e.asset_id == asset.id for e in all_exposures):
                assets_with_exposure.add(asset.id)

        if assets:
            coverage = round((len(assets_with_exposure) / len(assets)) * 100.0, 2)
        else:
            coverage = 100.0

        # 6. Map of individual exposures for drift tracking
        exposures_track = {}
        for e in all_exposures:
            exposures_track[str(e.exposure_id)] = {
                "exposure_id": str(e.exposure_id),
                "exposure_fingerprint": e.exposure_fingerprint,
                "severity": e.severity.value,
                "status": e.status.value,
                "risk_score": e.risk_score,
                "title": e.title,
            }

        snapshot = {
            "summary": {
                "total_exposures": total_exposures,
                "open_count": open_count,
                "critical_count": critical_count,
                "organization_risk_score": org_risk_score,
                "attack_surface_coverage": coverage,
            },
            "status_counts": status_counts,
            "exposures": exposures_track,
            "attack_surface": attack_surface_map,
        }

        cls._snapshots[scope_id] = snapshot
        return snapshot
