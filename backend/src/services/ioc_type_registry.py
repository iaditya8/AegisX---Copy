import re
from src.domain.entities.threat_intelligence import IOCType


class IOCTypeRegistry:
    # Regex patterns
    IP_PATTERN = re.compile(
        r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    )
    DOMAIN_PATTERN = re.compile(
        r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,6}$"
    )
    URL_PATTERN = re.compile(
        r"^https?://[a-zA-Z0-9.-]+(?::\d+)?(?:/[^\s]*)?$"
    )
    EMAIL_PATTERN = re.compile(
        r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    )
    MD5_PATTERN = re.compile(r"^[a-fA-F0-9]{32}$")
    SHA1_PATTERN = re.compile(r"^[a-fA-F0-9]{40}$")
    SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")

    @classmethod
    def validate_value(cls, ioc_type: IOCType, value: str) -> bool:
        """Validate an IOC value against its expected type format."""
        val = value.strip()
        if ioc_type == IOCType.IP_ADDRESS:
            return bool(cls.IP_PATTERN.match(val))
        elif ioc_type == IOCType.DOMAIN:
            return bool(cls.DOMAIN_PATTERN.match(val))
        elif ioc_type == IOCType.URL:
            return bool(cls.URL_PATTERN.match(val))
        elif ioc_type == IOCType.EMAIL:
            return bool(cls.EMAIL_PATTERN.match(val))
        elif ioc_type == IOCType.MD5:
            return bool(cls.MD5_PATTERN.match(val))
        elif ioc_type == IOCType.SHA1:
            return bool(cls.SHA1_PATTERN.match(val))
        elif ioc_type == IOCType.SHA256:
            return bool(cls.SHA256_PATTERN.match(val))
        return False

    @classmethod
    def normalize_value(cls, ioc_type: IOCType, value: str) -> str:
        """Normalize an IOC value based on its type (e.g. lowercasing domains/emails/hashes)."""
        val = value.strip()
        if ioc_type in [IOCType.DOMAIN, IOCType.EMAIL, IOCType.URL]:
            return val.lower()
        if ioc_type in [IOCType.MD5, IOCType.SHA1, IOCType.SHA256]:
            return val.lower()
        return val
