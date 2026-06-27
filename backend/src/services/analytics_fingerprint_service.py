import hashlib
import uuid
from typing import Optional


class AnalyticsFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls,
        analytics_name: str,
        scope_id: Optional[uuid.UUID] = None,
    ) -> str:
        """Generate stable report fingerprint using SHA-256(analytics_name:scope_id)."""
        normalized_name = str(analytics_name).strip().lower()
        scope_str = str(scope_id) if scope_id else "global"

        payload = f"name:{normalized_name}|scope:{scope_str}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
