from typing import Set
from src.domain.entities.governance_risk_compliance import FrameworkType


class ComplianceFrameworkRegistry:
    FRAMEWORKS = {f.value for f in FrameworkType}

    @classmethod
    def list_frameworks(cls) -> Set[str]:
        """List all supported GRC frameworks."""
        return cls.FRAMEWORKS

    @classmethod
    def validate(cls, framework_type: str) -> bool:
        """Validate if a framework type is supported."""
        return str(framework_type).strip() in cls.FRAMEWORKS
