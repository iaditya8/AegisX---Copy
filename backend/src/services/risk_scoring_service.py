from typing import Any, Dict, List, Optional

from src.services.risk_factor_registry import RISK_FACTORS


class RiskScoringService:
    """Service to calculate risk scores, levels, and factor explanations for assets."""

    @classmethod
    def calculate_risk(
        cls,
        correlation_snapshot: Dict[str, Any],
        exposure_classification: Optional[str] = None,
        findings: Optional[List[Any]] = None,
        technologies: Optional[List[str]] = None,
        services: Optional[List[Any]] = None,
        asset_criticality: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Calculate risk parameters using the Correlation Snapshot and Risk Factor
        Registry. Clamps the final score between 0 and 100, maps to a risk level,
        and explains factor impacts.
        """
        explanations = []
        raw_score = 0

        # Retrieve risk factors list from correlation snapshot
        factors = correlation_snapshot.get("risk_factors", [])

        for factor in factors:
            if factor in RISK_FACTORS:
                impact = RISK_FACTORS[factor]
                raw_score += impact
                explanations.append({"factor": factor, "impact": impact})

        # Clamp the score between 0 and 100
        risk_score = min(max(raw_score, 0), 100)

        # Map to risk level
        # 0-24 LOW
        # 25-49 MEDIUM
        # 50-74 HIGH
        # 75-100 CRITICAL
        if risk_score <= 24:
            risk_level = "LOW"
        elif risk_score <= 49:
            risk_level = "MEDIUM"
        elif risk_score <= 74:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "explanations": explanations,
        }
