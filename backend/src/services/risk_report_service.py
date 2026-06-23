from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Asset
from src.services.asset_risk_snapshot_service import AssetRiskSnapshotService
from src.services.risk_history_service import RiskHistoryService


class RiskReportService:
    """Service to generate detailed risk reports consuming snapshot/history services."""

    @classmethod
    async def generate_risk_report(cls, db: AsyncSession) -> Dict[str, Any]:
        """Compile risk distributions, find critical and high-risk assets,

        and extract unified history.
        """
        # 1. Fetch active assets
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        res_assets = await db.execute(q_assets)
        assets = res_assets.scalars().all()

        risk_distribution = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        critical_assets = []
        high_risk_assets = []
        risk_history_list = []

        for asset in assets:
            # Consume AssetRiskSnapshotService
            snapshot = AssetRiskSnapshotService.get_snapshot(asset.id)
            if (
                snapshot.get("exposure") == "UNKNOWN"
                and snapshot.get("risk_score") == 0
            ):
                snapshot = await AssetRiskSnapshotService.generate_snapshot(
                    db, asset.id
                )

            risk_level = str(snapshot.get("risk_level", "LOW")).lower()
            if risk_level in risk_distribution:
                risk_distribution[risk_level] += 1

            asset_info = {
                "id": str(asset.id),
                "host": asset.host,
                "ip": asset.ip,
                "asset_type": asset.asset_type,
                "risk_score": snapshot.get("risk_score", 0),
                "risk_level": snapshot.get("risk_level", "LOW"),
                "criticality": snapshot.get("criticality", "LOW"),
            }

            if risk_level == "critical":
                critical_assets.append(asset_info)
            elif risk_level == "high":
                high_risk_assets.append(asset_info)

            # Consume RiskHistoryService
            history_entries = RiskHistoryService.get_history(asset.id)
            for entry in history_entries:
                entry_copy = dict(entry)
                entry_copy["asset_id"] = str(asset.id)
                entry_copy["host"] = asset.host
                entry_copy["ip"] = asset.ip
                risk_history_list.append(entry_copy)

        # Sort history by timestamp descending
        risk_history_list = sorted(
            risk_history_list, key=lambda x: x.get("timestamp", ""), reverse=True
        )

        return {
            "risk_distribution": risk_distribution,
            "critical_assets": critical_assets,
            "high_risk_assets": high_risk_assets,
            "risk_history": risk_history_list,
        }
