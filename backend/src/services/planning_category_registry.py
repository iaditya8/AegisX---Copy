class PlanningCategoryRegistry:
    _categories = {
        "IMMEDIATE_THREAT_CONTAINMENT",
        "COMPLIANCE_ALIGNMENT",
        "RISK_REDUCTION_CAMPAIGN",
        "POSTURE_HARDENING",
    }

    @classmethod
    def validate(cls, category: str) -> bool:
        """Validate if category is a valid plan category."""
        return str(category).strip().upper() in cls._categories
