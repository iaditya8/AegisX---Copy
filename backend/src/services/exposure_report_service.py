from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Asset
from src.services.asset_exposure_service import (
    AssetExposureService,
)
from src.services.correlation_snapshot_service import CorrelationSnapshotService


class ExposureReportService:
    """Service to generate detailed exposure reports by classification."""

    @classmethod
    async def generate_exposure_report(cls, db: AsyncSession) -> Dict[str, Any]:
        """Group assets by exposure class and calculate public exposure."""
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        res_assets = await db.execute(q_assets)
        assets = res_assets.scalars().all()

        external_assets = []
        internal_assets = []
        unknown_assets = []
        internet_exposed_count = 0

        for asset in assets:
            snapshot = CorrelationSnapshotService.get_snapshot(asset.id)
            if snapshot.get("exposure") == "UNKNOWN" and not snapshot.get("ports"):
                snapshot = await CorrelationSnapshotService.generate_snapshot(
                    db, asset.id
                )

            exposure_val = snapshot.get("exposure", "UNKNOWN")
            if exposure_val == "UNKNOWN":
                # Fallback to direct AssetExposureService classification
                classif = AssetExposureService.classify(asset)
                exposure_val = (
                    classif.value if hasattr(classif, "value") else str(classif)
                )

            asset_info = {
                "id": str(asset.id),
                "host": asset.host,
                "ip": asset.ip,
                "asset_type": asset.asset_type,
                "ports": snapshot.get("ports", []),
                "services": snapshot.get("services", []),
                "technologies": snapshot.get("technologies", []),
            }

            if exposure_val == "EXTERNAL":
                external_assets.append(asset_info)
                internet_exposed_count += 1
            elif exposure_val == "INTERNAL":
                internal_assets.append(asset_info)
            else:
                unknown_assets.append(asset_info)

        return {
            "external_assets": external_assets,
            "internal_assets": internal_assets,
            "unknown_assets": unknown_assets,
            "internet_exposed_count": internet_exposed_count,
        }
