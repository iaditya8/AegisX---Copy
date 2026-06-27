import hashlib
import uuid
from typing import Optional


class RiskQuantificationFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls,
        scenario_type: str,
        title: str,
        scope_id: Optional[uuid.UUID] = None,
    ) -> str:
        """Generate stable report fingerprint using SHA-256(scenario_type:scope_id:title)."""
        normalized_title = str(title).strip().lower()
        normalized_scenario = str(scenario_type).strip().upper()
        scope_str = str(scope_id) if scope_id else "global"

        payload = f"scenario:{normalized_scenario}|scope:{scope_str}|title:{normalized_title}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
