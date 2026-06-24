import hashlib
from typing import Optional


class MonitoringFingerprintService:
    @classmethod
    def calculate_fingerprint(
        cls,
        change_type: str,
        asset_id: str,
        finding_id: Optional[str],
        previous_state: Optional[str],
        current_state: Optional[str],
    ) -> str:
        """Generate a deterministic SHA-256 fingerprint for a monitoring event."""
        fid = str(finding_id) if finding_id else ""
        prev = str(previous_state) if previous_state else ""
        curr = str(current_state) if current_state else ""
        raw_str = f"{change_type}:{str(asset_id)}:{fid}:{prev}:{curr}"
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
