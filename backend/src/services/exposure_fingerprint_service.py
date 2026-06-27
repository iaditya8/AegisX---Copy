import hashlib
import uuid
from src.domain.entities.exposure import ExposureType


class ExposureFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls, exposure_type: ExposureType, asset_id: uuid.UUID, target: str
    ) -> str:
        """Generate a stable deterministic SHA-256 fingerprint for an exposure."""
        normalized_target = str(target).strip().lower()
        payload = f"type:{exposure_type.value}|asset:{str(asset_id)}|target:{normalized_target}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
