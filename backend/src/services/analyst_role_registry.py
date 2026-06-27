from typing import Set


class AnalystRoleRegistry:
    ROLES = {
        "TIER1_ANALYST",
        "TIER2_ANALYST",
        "TIER3_ANALYST",
        "INCIDENT_RESPONDER",
        "THREAT_HUNTER",
        "SOC_MANAGER",
    }

    @classmethod
    def list_roles(cls) -> Set[str]:
        """List all supported analyst roles."""
        return cls.ROLES

    @classmethod
    def validate(cls, role_name: str) -> bool:
        """Validate if a role name is supported."""
        return str(role_name).strip() in cls.ROLES
