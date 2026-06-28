from typing import Set


class ThreatSourceRegistry:
    SOURCES = {
        "OSINT",
        "COMMERCIAL",
        "INTERNAL_HONEYPOT",
        "PARTNER_FEED",
        "NATIONAL_CERT",
    }

    @classmethod
    def list_sources(cls) -> Set[str]:
        """List all supported threat intelligence sources."""
        return cls.SOURCES

    @classmethod
    def validate(cls, source: str) -> bool:
        """Validate if a source is supported."""
        return str(source).strip().upper() in cls.SOURCES
