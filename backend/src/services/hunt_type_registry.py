from typing import Set

from src.domain.entities.hunt import HuntType


class HuntTypeRegistry:
    TYPES = {
        HuntType.IOC_DRIVEN: "Threat hunt triggered by indicators of compromise",
        HuntType.ATTACK_DRIVEN: "Threat hunt driven by MITRE ATT&CK techniques",
        HuntType.DETECTION_GAP: "Threat hunt targeting identified gaps in coverage",
        HuntType.THREAT_ACTOR_DRIVEN: "Threat hunt targeting profiles of threat actors",
        HuntType.CAMPAIGN_DRIVEN: "Threat hunt targeting active campaigns",
        HuntType.MANUAL: "Manual ad-hoc threat hunt",
    }

    @classmethod
    def get_registered_types(cls) -> Set[HuntType]:
        """Retrieve all registered hunt types."""
        return set(cls.TYPES.keys())

    @classmethod
    def is_valid_type(cls, hunt_type: str) -> bool:
        """Check if a hunt type is valid and registered."""
        try:
            val = HuntType(hunt_type)
            return val in cls.TYPES
        except ValueError:
            return False
