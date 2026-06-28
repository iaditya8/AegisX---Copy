class IntelligenceSourceRegistry:
    _sources = {
        "ASSET",
        "RISK",
        "GRC",
        "POSTURE",
        "RESILIENCE",
        "KNOWLEDGE",
        "THREAT_INTEL",
        "INCIDENT",
        "CASE",
    }

    @classmethod
    def validate(cls, source_type: str) -> bool:
        """Validate if source_type is a valid intelligence source."""
        return str(source_type).strip().upper() in cls._sources
