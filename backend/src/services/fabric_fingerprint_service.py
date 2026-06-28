import hashlib
import uuid
from typing import Optional


class FabricFingerprintService:
    @classmethod
    def generate_fingerprint(cls, source_type: str, scope_id: Optional[uuid.UUID] = None, rules_hash: str = "") -> str:
        """Generate stable SHA-256 fingerprint for a fabric intelligence node or channel."""
        scope_str = str(scope_id).strip().lower() if scope_id else "global"
        raw = f"{source_type.strip().upper()}_{scope_str}_{rules_hash.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
class FingerprintService(FabricFingerprintService):
    pass
