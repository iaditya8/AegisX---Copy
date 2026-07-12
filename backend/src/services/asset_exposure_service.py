import ipaddress
from typing import Any
from enum import Enum

from src.infrastructure.database.models import Asset

SUPPORTED_EXPOSURE_CLASSES = {
    "INTERNAL",
    "EXTERNAL",
    "UNKNOWN",
}


class ExposureClassification(str, Enum):
    INTERNAL = "INTERNAL"
    EXTERNAL = "EXTERNAL"
    UNKNOWN = "UNKNOWN"


class AssetExposureService:
    """Service to classify assets into ExposureClassification levels."""

    @staticmethod
    def is_public_ip(ip_str: Any) -> bool:
        """Check if an IP address is public (not private, loopback, or link-local)."""
        if not ip_str:
            return False
        try:
            # Safely coerce to string in case it's an ipaddress object from SQLAlchemy INET type
            val = str(ip_str).strip()
            ip = ipaddress.ip_address(val)
            # Public if it's not private, loopback, or link-local
            return not (ip.is_private or ip.is_loopback or ip.is_link_local)
        except ValueError:
            return False

    @staticmethod
    def is_internal_hostname(host_str: str) -> bool:
        """Check if hostname matches internal/private naming suffixes."""
        if not host_str:
            return True
        host_lower = host_str.strip().lower()
        internal_suffixes = [
            ".local",
            ".internal",
            ".lan",
            ".localdomain",
            ".home",
            ".intranet",
            ".private",
            "localhost",
        ]
        for suffix in internal_suffixes:
            if host_lower.endswith(suffix) or host_lower == suffix:
                return True
        return False

    @classmethod
    def _is_public_asset(cls, asset: Asset) -> bool:
        """Check if an asset has public exposure.

        Determined by having a public IP or an internet-facing hostname.
        """
        ip = asset.ip
        host = asset.host
        if ip and cls.is_public_ip(ip):
            return True
        if host and not cls.is_internal_hostname(host):
            return True
        return False

    @classmethod
    def _is_internal_asset(cls, asset: Asset) -> bool:
        """Check if an asset is purely internally exposed.

        Determined by having an RFC1918/local IP or internal naming suffix,
        without having any public/internet-facing properties.
        """
        ip = asset.ip
        host = asset.host
        if cls._is_public_asset(asset):
            return False
        has_internal_ip = ip and not cls.is_public_ip(ip)
        has_internal_host = host and cls.is_internal_hostname(host)
        if has_internal_ip or has_internal_host:
            return True
        return False

    @classmethod
    def classify(cls, asset: Asset) -> ExposureClassification:
        """Classify the asset's exposure based on its IP and hostname.

        Logic checks for external/public attributes first, then internal, and
        defaults to unknown. Structuring logic here allows future extension
        points (like HYBRID classification) to easily inspect public/private
        mixes without modifying class interfaces.
        """
        if not asset.ip and not asset.host:
            return ExposureClassification.UNKNOWN

        # Future HYBRID support could check for mixed conditions:
        # e.g., if cls._is_hybrid_asset(asset): return ExposureClassification.HYBRID

        if cls._is_public_asset(asset):
            return ExposureClassification.EXTERNAL

        if cls._is_internal_asset(asset):
            return ExposureClassification.INTERNAL

        return ExposureClassification.UNKNOWN
