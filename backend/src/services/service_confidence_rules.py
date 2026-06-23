class ServiceConfidenceRules:
    """Centralized rules for assigning confidence to discovered services and ports."""

    @staticmethod
    def get_port_confidence() -> float:
        """Ports discovered by naabu/nmap are highly confident if marked open."""
        return 1.0

    @staticmethod
    def get_service_confidence(
        has_version: bool = False,
        has_product: bool = False,
        has_banner: bool = False,
        service_name: str = "unknown",
    ) -> float:
        """Calculate confidence based on extracted data richness."""
        if has_version and has_product:
            return 0.95
        if has_banner or has_product:
            return 0.85
        if service_name and service_name != "unknown":
            return 0.80
        return 0.50
