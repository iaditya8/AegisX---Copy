import uuid
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.services.asset_criticality_service import AssetCriticalityService
from src.services.correlation_snapshot_service import CorrelationSnapshotService
from src.services.risk_history_service import RiskHistoryService
from src.services.risk_scoring_service import RiskScoringService


class AssetRiskSnapshotService:
    """In-memory cache and service for asset risk snapshots."""

    # In-memory store for snapshots
    _snapshots: Dict[uuid.UUID, Dict[str, Any]] = {}

    @classmethod
    async def generate_snapshot(
        cls, db: AsyncSession, asset_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Generate a complete asset risk snapshot by combining correlation,
        criticality, and scoring services.
        """
        # 1. Fetch/generate correlation snapshot
        corr_snapshot = CorrelationSnapshotService.get_snapshot(asset_id)
        if not corr_snapshot or (
            not corr_snapshot.get("ports")
            and corr_snapshot.get("exposure") == "UNKNOWN"
        ):
            corr_snapshot = await CorrelationSnapshotService.generate_snapshot(
                db, asset_id
            )

        # 2. Calculate criticality details
        crit_data = await AssetCriticalityService.calculate_asset_criticality(
            db, asset_id
        )
        criticality_val = crit_data.get("criticality", "LOW")
        if hasattr(criticality_val, "value"):
            criticality_val = criticality_val.value

        # 3. Calculate risk parameters
        risk_data = RiskScoringService.calculate_risk(
            correlation_snapshot=corr_snapshot,
            exposure_classification=corr_snapshot.get("exposure"),
            asset_criticality=crit_data,
        )

        exposure_val = corr_snapshot.get("exposure", "UNKNOWN")
        if hasattr(exposure_val, "value"):
            exposure_val = exposure_val.value

        snapshot = {
            "asset_id": str(asset_id),
            "criticality": criticality_val,
            "risk_score": risk_data.get("risk_score", 0),
            "risk_level": risk_data.get("risk_level", "LOW"),
            "exposure": exposure_val,
            "finding_counts": corr_snapshot.get("finding_counts", {}),
            "risk_factors": corr_snapshot.get("risk_factors", []),
            "explanations": risk_data.get("explanations", []),
        }

        return snapshot

    @classmethod
    async def update_snapshot(
        cls,
        db: AsyncSession,
        asset_id: uuid.UUID,
        scan_run_id: Optional[uuid.UUID] = None,
        workflow_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Recompute and cache the risk snapshot. Records changes in RiskHistoryService.
        """
        old_snapshot = cls._snapshots.get(asset_id)
        snapshot = await cls.generate_snapshot(db, asset_id)
        cls._snapshots[asset_id] = snapshot

        # Record changes in the Risk History Service (which handles events & audit logs)
        await RiskHistoryService.record_history(
            db=db,
            asset_id=asset_id,
            new_score=snapshot["risk_score"],
            new_level=snapshot["risk_level"],
            new_criticality=snapshot["criticality"],
            scan_run_id=scan_run_id,
            workflow_id=workflow_id,
        )

        changed = (
            old_snapshot is None
            or old_snapshot.get("risk_score") != snapshot.get("risk_score")
            or old_snapshot.get("risk_level") != snapshot.get("risk_level")
            or old_snapshot.get("exposure") != snapshot.get("exposure")
            or old_snapshot.get("criticality") != snapshot.get("criticality")
        )

        if changed:
            from src.services.recommendation_snapshot_service import (
                RecommendationSnapshotService,
            )

            await RecommendationSnapshotService.update_snapshot(db, asset_id)

            from src.services.report_cache_service import ReportCacheService

            ReportCacheService.invalidate_for_asset(asset_id)

        return snapshot

    @classmethod
    def get_snapshot(cls, asset_id: uuid.UUID) -> Dict[str, Any]:
        """Retrieve the cached asset risk snapshot."""
        return cls._snapshots.get(
            asset_id,
            {
                "asset_id": str(asset_id),
                "criticality": "LOW",
                "risk_score": 0,
                "risk_level": "LOW",
                "exposure": "UNKNOWN",
                "finding_counts": {},
                "risk_factors": [],
                "explanations": [],
            },
        )
