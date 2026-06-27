import hashlib
import uuid
from typing import Optional


class ComplianceFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls,
        framework_type: str,
        name: str,
        scope_id: Optional[uuid.UUID] = None,
    ) -> str:
        """Generate stable GRC report fingerprint using SHA-256."""
        normalized_name = str(name).strip().lower()
        normalized_framework = str(framework_type).strip().upper()
        scope_str = str(scope_id) if scope_id else "global"

        payload = f"framework:{normalized_framework}|scope:{scope_str}|name:{normalized_name}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
