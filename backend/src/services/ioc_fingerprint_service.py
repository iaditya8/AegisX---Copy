import hashlib

from src.domain.entities.threat_intelligence import IOCType
from src.services.ioc_type_registry import IOCTypeRegistry


class IOCFingerprintService:
    @classmethod
    def generate_fingerprint(cls, ioc_type: IOCType, value: str) -> str:
        """Generate a stable, deterministic SHA-256 fingerprint for an IOC."""
        normalized_value = IOCTypeRegistry.normalize_value(ioc_type, value)
        payload = f"type:{ioc_type.value}|value:{normalized_value}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
