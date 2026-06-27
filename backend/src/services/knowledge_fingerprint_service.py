import hashlib
import uuid
from typing import Optional


class KnowledgeFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls,
        knowledge_type: str,
        title: str,
        scope_id: Optional[uuid.UUID] = None,
    ) -> str:
        """Generate stable GRC knowledge fingerprint using SHA-256."""
        normalized_title = str(title).strip().lower()
        normalized_type = str(knowledge_type).strip().upper()
        scope_str = str(scope_id) if scope_id else "global"

        payload = f"type:{normalized_type}|scope:{scope_str}|title:{normalized_title}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
