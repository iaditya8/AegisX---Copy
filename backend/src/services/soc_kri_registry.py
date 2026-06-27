from typing import Set


class SOCKRIRegistry:
    KRIS = {
        "Alert Backlog Growth",
        "Incident Backlog Growth",
        "Case Backlog Growth",
        "Escalation Growth",
        "SLA Breach Growth",
        "Critical Alert Growth",
    }

    @classmethod
    def list_types(cls) -> Set[str]:
        """List all supported operational KRIs."""
        return cls.KRIS

    @classmethod
    def validate(cls, kri_name: str) -> bool:
        """Validate if a KRI is supported."""
        return str(kri_name).strip() in cls.KRIS
