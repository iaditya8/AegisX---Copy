from typing import Set


class SecurityProgramRegistry:
    CATEGORIES = {
        "Vulnerability Management",
        "Incident Response",
        "Identity Governance",
        "Threat Intelligence",
        "Control Validation",
    }

    @classmethod
    def get_categories(cls) -> Set[str]:
        """Retrieve all supported security program categories."""
        return cls.CATEGORIES

    @classmethod
    def is_valid_category(cls, category: str) -> bool:
        """Check if a category is valid."""
        return str(category).strip() in cls.CATEGORIES
