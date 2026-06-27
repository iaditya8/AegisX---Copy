from typing import Any, Set, Union
from src.domain.entities.control_validation import ControlType


class ControlTypeRegistry:
    @classmethod
    def get_registered_types(cls) -> Set[ControlType]:
        """Retrieve all registered control types."""
        return set(ControlType)

    @classmethod
    def is_valid_type(cls, control_type: Any) -> bool:
        """Check if a control type is valid."""
        if isinstance(control_type, ControlType):
            return True
        try:
            ControlType(str(control_type).upper())
            return True
        except ValueError:
            return False

    @classmethod
    def resolve_type(cls, control_type: Union[ControlType, str]) -> ControlType:
        """Resolve string/enum to ControlType, defaulting to MONITORING."""
        if isinstance(control_type, ControlType):
            return control_type
        try:
            return ControlType(str(control_type).upper())
        except ValueError:
            return ControlType.MONITORING
