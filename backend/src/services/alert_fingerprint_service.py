import hashlib
import uuid
from typing import Optional


class AlertFingerprintService:
    @classmethod
    def calculate_fingerprint(
        cls,
        alert_type: str,
        asset_id: Optional[uuid.UUID],
        finding_id: Optional[uuid.UUID] = None,
        recommendation_id: Optional[uuid.UUID] = None,
        remediation_id: Optional[uuid.UUID] = None,
    ) -> str:
        """Generate a deterministic SHA-256 fingerprint for an alert."""
        aid = str(asset_id) if asset_id else ""
        fid = str(finding_id) if finding_id else ""
        rec_id = str(recommendation_id) if recommendation_id else ""
        rem_id = str(remediation_id) if remediation_id else ""

        raw_str = f"{str(alert_type)}:{aid}:{fid}:{rec_id}:{rem_id}"
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
