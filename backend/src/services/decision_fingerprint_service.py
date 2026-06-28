import hashlib
import uuid
from src.domain.entities.security_decision import DecisionType


class DecisionFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls, decision_type: DecisionType, target_entity_id: uuid.UUID, option_name: str
    ) -> str:
        """Generate stable SHA-256 fingerprint for a security decision."""
        type_str = decision_type.value if hasattr(decision_type, "value") else str(decision_type)
        raw = f"{type_str.strip().upper()}_{str(target_entity_id).strip().lower()}_{option_name.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
