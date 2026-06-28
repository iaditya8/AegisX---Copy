from typing import Set
from src.domain.entities.threat_intel import ThreatIndicatorType


class ThreatIndicatorTypeRegistry:
    TYPES = {t.value for t in ThreatIndicatorType}

    @classmethod
    def list_types(cls) -> Set[str]:
        """List all supported indicator types."""
        return cls.TYPES

    @classmethod
    def validate(cls, indicator_type: str) -> bool:
        """Validate if indicator type is supported."""
        return str(indicator_type).strip().upper() in cls.TYPES
