import uuid
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.loss_expectancy_service import LossExpectancyService
from src.services.residual_risk_service import ResidualRiskService
from src.services.risk_forecast_service import RiskForecastService


class RiskQuantificationSnapshotService:
    # Cache store: scope_id -> Snapshot dictionary
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear the snapshot cache."""
        cls._snapshots.clear()

    @classmethod
    def get_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Retrieve the cached snapshot, defaulting to a minimal fallback if missing or corrupted."""
        snap = cls._snapshots.get(scope_id)
        if not snap or not isinstance(snap, dict) or "summary" not in snap:
            return {
                "summary": {
                    "total_risk_records": 0,
                    "active_risk_records": 0,
                    "closed_risk_records": 0,
                    "total_exposure_value": 0.0,
                    "total_annualized_loss_expectancy": 0.0,
                    "average_inherent_risk_score": 0.0,
                    "average_residual_risk_score": 0.0,
                    "projected_loss_forecast": 0.0,
                },
                "records": {},
            }
        return snap

    @classmethod
    async def generate_snapshot(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None
    ) -> dict:
        """Dynamically rebuild snapshot stats from active quantified risks."""
        from src.services.cyber_risk_quantification_service import CyberRiskQuantificationService
        from src.domain.entities.cyber_risk_quantification import RiskQuantificationStatus

        all_recs = CyberRiskQuantificationService.get_all_risks()
        if scope_id:
            all_recs = [r for r in all_recs if r.scope_id == scope_id]

        total_recs = len(all_recs)
        active_count = sum(1 for r in all_recs if r.status in (RiskQuantificationStatus.ACTIVE, RiskQuantificationStatus.ACCEPTED, RiskQuantificationStatus.MITIGATED))
        closed_count = sum(1 for r in all_recs if r.status == RiskQuantificationStatus.CLOSED)

        total_exposure = sum(r.exposure_value for r in all_recs)
        total_ale = sum(r.annualized_loss_expectancy for r in all_recs)

        avg_inherent = (
            round(sum(r.inherent_risk_score for r in all_recs) / total_recs, 2)
            if total_recs > 0
            else 0.0
        )
        avg_residual = (
            round(sum(r.residual_risk_score for r in all_recs) / total_recs, 2)
            if total_recs > 0
            else 0.0
        )

        # Average Q1 projected loss forecast
        proj_sum = 0.0
        for r in all_recs:
            forecasts = RiskForecastService.get_forecasts(r.risk_id, r.annualized_loss_expectancy, r.exposure_value)
            if forecasts:
                proj_sum += forecasts[0].projected_loss
        avg_projected = round(proj_sum / total_recs, 2) if total_recs > 0 else 0.0

        records_track = {}
        for r in all_recs:
            records_track[str(r.risk_id)] = {
                "risk_id": str(r.risk_id),
                "title": r.title,
                "status": r.status.value,
                "exposure_value": r.exposure_value,
                "annualized_loss_expectancy": r.annualized_loss_expectancy,
                "residual_risk_score": r.residual_risk_score,
            }

        snapshot = {
            "summary": {
                "total_risk_records": total_recs,
                "active_risk_records": active_count,
                "closed_risk_records": closed_count,
                "total_exposure_value": total_exposure,
                "total_annualized_loss_expectancy": total_ale,
                "average_inherent_risk_score": avg_inherent,
                "average_residual_risk_score": avg_residual,
                "projected_loss_forecast": avg_projected,
            },
            "records": records_track,
        }

        cls._snapshots[scope_id] = snapshot
        return snapshot
