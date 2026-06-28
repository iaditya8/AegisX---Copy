import hashlib
import uuid
from typing import Optional


class PlanningFingerprintService:
    @classmethod
    def generate_fingerprint(cls, category: str, name: str, scope_id: Optional[uuid.UUID] = None) -> str:
        """Generate stable SHA-256 fingerprint for a planning record."""
        scope_str = str(scope_id).strip().lower() if scope_id else "global"
        raw = f"{category.strip().upper()}_{scope_str}_{name.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
