from typing import Any, Dict


class RecommendationRulesRegistry:
    # Deterministic rules mapping states to recommendations
    RULES: Dict[str, Dict[str, Any]] = {
        "external_critical_finding": {
            "type": "PATCH",
            "priority": "CRITICAL",
            "title": "Patch internet-facing critical vulnerability",
            "reason": "Critical finding exists on an external asset",
        },
        "high_risk_asset": {
            "type": "HARDEN",
            "priority": "HIGH",
            "title": "Harden high-risk asset configuration",
            "reason": "Asset risk score exceeds critical threshold (risk_score >= 80)",
        },
        "rediscovered_finding": {
            "type": "INVESTIGATE",
            "priority": "HIGH",
            "title": "Investigate rediscovered vulnerability",
            "reason": "Finding has re-occurred or been reopened across scans",
        },
        "critical_finding": {
            "type": "PATCH",
            "priority": "HIGH",
            "title": "Patch critical vulnerability",
            "reason": "Critical severity finding detected",
        },
        "high_finding": {
            "type": "PATCH",
            "priority": "MEDIUM",
            "title": "Patch high severity vulnerability",
            "reason": "High severity finding detected",
        },
        "medium_finding": {
            "type": "REVIEW",
            "priority": "MEDIUM",
            "title": "Review medium severity finding",
            "reason": "Medium severity finding detected",
        },
        "low_finding": {
            "type": "MONITOR",
            "priority": "LOW",
            "title": "Monitor low severity finding",
            "reason": "Low severity finding detected",
        },
    }

    @classmethod
    def get_rule(cls, state_key: str) -> Dict[str, Any]:
        """Retrieve a specific recommendation rule configuration."""
        return cls.RULES.get(state_key, {})
