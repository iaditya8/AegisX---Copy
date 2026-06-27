from typing import Set


class ResilienceRegistry:
    CATEGORIES = {
        "BUSINESS_CONTINUITY",
        "DISASTER_RECOVERY",
        "RECOVERY_VALIDATION",
        "RECOVERY_READINESS",
        "SERVICE_RESILIENCE",
    }

    @classmethod
    def list_types(cls) -> Set[str]:
        """List all supported resilience categories."""
        return cls.CATEGORIES

    @classmethod
    def validate(cls, category: str) -> bool:
        """Validate if a category is supported."""
        return str(category).strip() in cls.CATEGORIES
