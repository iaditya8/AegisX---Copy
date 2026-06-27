import uuid
from typing import Dict, Any
from src.domain.entities.security_posture import PostureSeverity, RiskCategory


class RiskIntelligenceService:
    @classmethod
    def calculate_risk(
        cls, asset_id: uuid.UUID, category: RiskCategory, severity: PostureSeverity
    ) -> Dict[str, Any]:
        """Aggregate risks and calculate deterministic likelihood, impact, and risk score."""
        # Likelihood mapping
        likelihood_map = {
            PostureSeverity.CRITICAL: 0.95,
            PostureSeverity.HIGH: 0.75,
            PostureSeverity.MEDIUM: 0.50,
            PostureSeverity.LOW: 0.25,
        }
        likelihood = likelihood_map.get(severity, 0.25)

        # Impact mapping
        impact_map = {
            PostureSeverity.CRITICAL: 0.90,
            PostureSeverity.HIGH: 0.70,
            PostureSeverity.MEDIUM: 0.50,
            PostureSeverity.LOW: 0.30,
        }
        impact = impact_map.get(severity, 0.30)

        # Category multiplier to adjust impact based on business categories
        category_weights = {
            RiskCategory.THREAT_EXPOSURE: 1.1,
            RiskCategory.ATTACK_SURFACE: 1.0,
            RiskCategory.VULNERABILITY: 1.0,
            RiskCategory.DETECTION_GAP: 0.9,
            RiskCategory.COMPLIANCE: 0.8,
            RiskCategory.IDENTITY: 0.9,
            RiskCategory.CONFIGURATION: 0.8,
            RiskCategory.OPERATIONAL: 0.7,
        }
        weight = category_weights.get(category, 1.0)
        adjusted_impact = min(round(impact * weight, 2), 1.0)

        # Risk score out of 100
        risk_score = round(likelihood * adjusted_impact * 100.0, 2)

        # Posture score is inverse of risk score (i.e. lower risk = higher posture)
        posture_score = round(100.0 - risk_score, 2)

        return {
            "likelihood": likelihood,
            "impact": adjusted_impact,
            "risk_score": risk_score,
            "posture_score": posture_score,
        }
