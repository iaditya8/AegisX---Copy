import uuid
from typing import List
from src.domain.entities.governance_risk_compliance import FrameworkType, FrameworkControlResponse
from src.services.control_mapping_registry import ControlMappingRegistry


class FrameworkMappingService:
    @classmethod
    def get_mappings(cls, framework: FrameworkType) -> List[FrameworkControlResponse]:
        return ControlMappingRegistry.get_controls(framework)

    @classmethod
    def calculate(cls) -> None:
        """Deprecated placeholder calculation method."""
        pass
