import hashlib
import uuid
from typing import List


class CaseFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls,
        incident_ids: List[uuid.UUID],
        alert_ids: List[uuid.UUID],
        asset_ids: List[uuid.UUID],
    ) -> str:
        """Generate a stable, deterministic SHA-256 fingerprint for a case based on incident, alert, and asset IDs."""
        sorted_incidents = sorted([str(uid) for uid in set(incident_ids) if uid])
        sorted_alerts = sorted([str(uid) for uid in set(alert_ids) if uid])
        sorted_assets = sorted([str(uid) for uid in set(asset_ids) if uid])

        payload = (
            f"incidents:{','.join(sorted_incidents)}|"
            f"alerts:{','.join(sorted_alerts)}|"
            f"assets:{','.join(sorted_assets)}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
