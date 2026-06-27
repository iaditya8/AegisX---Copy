import uuid
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.exposure import ExposureSeverity
from src.services.asset_risk_snapshot_service import AssetRiskSnapshotService


class ExposurePrioritizationService:
    @classmethod
    async def calculate_exposure_priority(
        cls, db: AsyncSession, asset_id: uuid.UUID, severity: ExposureSeverity
    ) -> Dict[str, Any]:
        """Calculate risk score, likelihood, and impact score for an exposure."""
        # 1. Likelihood based on exposure severity
        likelihood_map = {
            ExposureSeverity.CRITICAL: 0.9,
            ExposureSeverity.HIGH: 0.7,
            ExposureSeverity.MEDIUM: 0.5,
            ExposureSeverity.LOW: 0.3,
        }
        likelihood = likelihood_map.get(severity, 0.3)

        # 2. Impact based on asset criticality
        risk_snapshot = AssetRiskSnapshotService.get_snapshot(asset_id)
        criticality = str(risk_snapshot.get("criticality", "LOW")).upper()

        impact_map = {
            "CRITICAL": 0.9,
            "HIGH": 0.8,
            "MEDIUM": 0.5,
            "LOW": 0.2,
        }
        impact = impact_map.get(criticality, 0.2)

        # Calculate risk score out of 100.0
        risk_score = round(likelihood * impact * 100.0, 2)

        return {
            "likelihood": likelihood,
            "impact": impact,
            "risk_score": risk_score,
            "criticality": criticality,
        }
