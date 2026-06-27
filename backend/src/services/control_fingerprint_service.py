import hashlib
from typing import List
from src.domain.entities.control_validation import ControlType


class ControlFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls, name: str, attack_techniques: List[str], control_type: ControlType
    ) -> str:
        """Generate stable control fingerprint using SHA-256(control_name:sorted_attack_techniques:control_type)."""
        normalized_name = str(name).strip().lower()
        sorted_techs = ",".join(sorted(str(t).strip().upper() for t in attack_techniques))
        payload = f"name:{normalized_name}|techs:{sorted_techs}|type:{control_type.value}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
