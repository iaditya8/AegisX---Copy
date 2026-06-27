from typing import Any, Set, Union
from src.domain.entities.purple_team import ValidationStatus


class ValidationStatusRegistry:
    @classmethod
    def get_registered_statuses(cls) -> Set[ValidationStatus]:
        """Retrieve all registered validation statuses."""
        return set(ValidationStatus)

    @classmethod
    def is_valid_status(cls, status: Any) -> bool:
        """Check if a status is registered/valid."""
        if isinstance(status, ValidationStatus):
            return True
        try:
            ValidationStatus(str(status).upper())
            return True
        except ValueError:
            return False

    @classmethod
    def resolve_status(cls, status: Union[ValidationStatus, str]) -> ValidationStatus:
        """Resolve string/enum to ValidationStatus, defaulting to FAILED."""
        if isinstance(status, ValidationStatus):
            return status
        try:
            return ValidationStatus(str(status).upper())
        except ValueError:
            return ValidationStatus.FAILED
