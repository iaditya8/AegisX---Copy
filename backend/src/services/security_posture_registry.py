from typing import Any, Set, Union
from src.domain.entities.security_posture import RiskCategory


class SecurityPostureRegistry:
    @classmethod
    def get_registered_categories(cls) -> Set[RiskCategory]:
        """Retrieve all registered risk/posture categories."""
        return set(RiskCategory)

    @classmethod
    def is_valid_category(cls, category: Any) -> bool:
        """Check if a category is valid/registered."""
        if isinstance(category, RiskCategory):
            return True
        try:
            RiskCategory(str(category).upper())
            return True
        except ValueError:
            return False

    @classmethod
    def resolve_category(cls, category: Union[RiskCategory, str]) -> RiskCategory:
        """Resolve string/enum to RiskCategory, defaulting to OPERATIONAL."""
        if isinstance(category, RiskCategory):
            return category
        try:
            return RiskCategory(str(category).upper())
        except ValueError:
            return RiskCategory.OPERATIONAL
