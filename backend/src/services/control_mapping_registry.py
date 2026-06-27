import uuid
from typing import Dict, List
from src.domain.entities.governance_risk_compliance import FrameworkType, FrameworkControlResponse


class ControlMappingRegistry:
    # in-memory pre-seeded control maps: framework -> list of controls
    _mappings: Dict[FrameworkType, List[FrameworkControlResponse]] = {}

    @classmethod
    def initialize_registry(cls) -> None:
        """Initialize standard pre-seeded framework controls."""
        cls._mappings = {
            FrameworkType.ISO27001: [
                FrameworkControlResponse(
                    control_id=uuid.uuid4(),
                    control_name="Access Control Policy",
                    framework_type=FrameworkType.ISO27001,
                    requirement_id="A.9.1.1",
                    status="MAPPED",
                ),
                FrameworkControlResponse(
                    control_id=uuid.uuid4(),
                    control_name="Information Security Incident Management",
                    framework_type=FrameworkType.ISO27001,
                    requirement_id="A.16.1.1",
                    status="MAPPED",
                ),
            ],
            FrameworkType.SOC2: [
                FrameworkControlResponse(
                    control_id=uuid.uuid4(),
                    control_name="Logical Access Controls",
                    framework_type=FrameworkType.SOC2,
                    requirement_id="CC6.1",
                    status="MAPPED",
                ),
                FrameworkControlResponse(
                    control_id=uuid.uuid4(),
                    control_name="Risk Assessment Process",
                    framework_type=FrameworkType.SOC2,
                    requirement_id="CC3.1",
                    status="MAPPED",
                ),
            ],
        }

    @classmethod
    def get_controls(cls, framework: FrameworkType) -> List[FrameworkControlResponse]:
        """Get controls pre-seeded for a framework."""
        if not cls._mappings:
            cls.initialize_registry()
        return cls._mappings.get(framework, [])

    @classmethod
    def validate_control(cls, framework: FrameworkType, control_name: str) -> bool:
        """Validate if control belongs to framework."""
        controls = cls.get_controls(framework)
        return any(c.control_name.lower() == control_name.lower() for c in controls)
