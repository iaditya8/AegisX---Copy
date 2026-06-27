import hashlib
from src.domain.entities.security_program import ProgramSeverity


class ProgramFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls, name: str, category: str, severity: ProgramSeverity
    ) -> str:
        """Generate stable security program fingerprint using SHA-256(name:category:severity)."""
        normalized_name = str(name).strip().lower()
        normalized_cat = str(category).strip().lower()
        payload = f"name:{normalized_name}|cat:{normalized_cat}|sev:{severity.value}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
