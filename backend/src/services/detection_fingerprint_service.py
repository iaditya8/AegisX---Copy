import hashlib
from typing import List


class DetectionFingerprintService:
    @classmethod
    def generate_fingerprint(cls, name: str, attack_techniques: List[str]) -> str:
        """Generate a stable, deterministic SHA-256 fingerprint for a detection based on its name and sorted attack techniques."""
        cleaned_name = name.strip()
        sorted_techniques = sorted([str(t).strip() for t in set(attack_techniques) if t])
        payload = f"name:{cleaned_name}|techniques:{','.join(sorted_techniques)}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
