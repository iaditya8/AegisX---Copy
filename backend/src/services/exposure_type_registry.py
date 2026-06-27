from typing import Any, Set, Union
from src.domain.entities.exposure import ExposureType


class ExposureTypeRegistry:
    @classmethod
    def get_registered_types(cls) -> Set[ExposureType]:
        """Retrieve all registered exposure types."""
        return set(ExposureType)

    @classmethod
    def is_valid_type(cls, exposure_type: Any) -> bool:
        """Check if an exposure type is valid/registered."""
        if isinstance(exposure_type, ExposureType):
            return True
        try:
            ExposureType(str(exposure_type).upper())
            return True
        except ValueError:
            return False

    @classmethod
    def resolve_type(cls, exposure_type: Union[ExposureType, str]) -> ExposureType:
        """Resolve string/enum to ExposureType, defaulting to MISCONFIGURATION."""
        if isinstance(exposure_type, ExposureType):
            return exposure_type
        try:
            return ExposureType(str(exposure_type).upper())
        except ValueError:
            return ExposureType.MISCONFIGURATION
