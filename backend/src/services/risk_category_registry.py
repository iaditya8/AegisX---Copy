from typing import Set


class RiskCategoryRegistry:
    # Mapping of specific threat and compliance fields to standard risk categories
    MAPPINGS = {
        "ATTACK_SURFACE": "Exposed target systems, open ports, public hosts",
        "VULNERABILITY": "Software flaws, vulnerabilities, patch levels",
        "DETECTION_GAP": "Coverage gaps, unmonitored systems, logging failures",
        "THREAT_EXPOSURE": "Threat intelligence indicators, actors, campaigns, reputational threats",
        "COMPLIANCE": "Governance failures, non-compliance status, failed checks",
        "IDENTITY": "Weak identity configurations, excessive roles",
        "CONFIGURATION": "System misconfigurations, weak cipher suites",
        "OPERATIONAL": "Operational risks, remediation SLA breaches",
    }

    @classmethod
    def get_supported_classifications(cls) -> Set[str]:
        """Retrieve all supported risk classifications."""
        return set(cls.MAPPINGS.keys())

    @classmethod
    def is_supported(cls, classification: str) -> bool:
        """Check if classification is supported."""
        return str(classification).strip().upper() in cls.MAPPINGS
