from typing import Set
from src.domain.entities.security_knowledge import KnowledgeType


class KnowledgeTypeRegistry:
    TYPES = {t.value for t in KnowledgeType}

    @classmethod
    def list_types(cls) -> Set[str]:
        """List all supported knowledge types."""
        return cls.TYPES

    @classmethod
    def validate(cls, type_name: str) -> bool:
        """Validate if a knowledge type is supported."""
        return str(type_name).strip() in cls.TYPES
