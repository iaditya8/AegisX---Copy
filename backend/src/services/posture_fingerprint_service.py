import hashlib
import uuid
from src.domain.entities.security_posture import RiskCategory


class PostureFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls, category: RiskCategory, asset_id: uuid.UUID, risk_source: str
    ) -> str:
        """Generate stable security posture fingerprint using SHA-256(category:asset_id:normalized_risk_source)."""
        normalized_source = str(risk_source).strip().lower()
        payload = f"cat:{category.value}|asset:{str(asset_id)}|src:{normalized_source}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
