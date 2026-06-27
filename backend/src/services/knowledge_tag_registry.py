from typing import Set


class KnowledgeTagRegistry:
    TAGS = {
        "malware",
        "phishing",
        "ransomware",
        "lateral_movement",
        "credential_access",
        "persistence",
        "detection",
        "hunting",
        "incident_response",
        "forensics",
        "compliance",
    }

    @classmethod
    def list_tags(cls) -> Set[str]:
        """List all pre-seeded tags."""
        return cls.TAGS

    @classmethod
    def validate(cls, tag: str) -> bool:
        """Validate if tag is supported."""
        return str(tag).strip().lower() in cls.TAGS
