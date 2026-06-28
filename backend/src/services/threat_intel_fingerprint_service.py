import hashlib
import uuid
from typing import Optional


class ThreatIntelFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls,
        indicator_type: str,
        value: str,
        scope_id: Optional[uuid.UUID] = None,
    ) -> str:
        """Generate stable GRC threat intelligence fingerprint using SHA-256."""
        normalized_val = str(value).strip().lower()
        normalized_type = str(indicator_type).strip().upper()
        scope_str = str(scope_id) if scope_id else "global"

        payload = f"type:{normalized_type}|scope:{scope_str}|value:{normalized_val}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
