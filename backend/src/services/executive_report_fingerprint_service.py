import hashlib
import uuid
from typing import List, Optional


class ExecutiveReportFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls,
        report_period: str,
        scope_id: Optional[uuid.UUID] = None,
        included_entities: Optional[List[str]] = None,
    ) -> str:
        """Generate stable report fingerprint using SHA-256(report_period:scope_id:included_entities)."""
        normalized_period = str(report_period).strip().lower()
        scope_str = str(scope_id) if scope_id else "global"
        entities_list = sorted(list(included_entities or []))
        entities_str = ",".join(str(e).strip().lower() for e in entities_list)

        payload = f"period:{normalized_period}|scope:{scope_str}|entities:[{entities_str}]"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
