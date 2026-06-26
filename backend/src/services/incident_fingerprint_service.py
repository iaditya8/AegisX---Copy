import hashlib
import uuid
from typing import List


class IncidentFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls,
        alert_ids: List[uuid.UUID],
        asset_ids: List[uuid.UUID],
        finding_ids: List[uuid.UUID],
    ) -> str:
        """Generate a stable, deterministic SHA-256 fingerprint for an incident."""
        # Sort and deduplicate all UUIDs to ensure stable hash output
        sorted_alerts = sorted([str(uid) for uid in set(alert_ids) if uid])
        sorted_assets = sorted([str(uid) for uid in set(asset_ids) if uid])
        sorted_findings = sorted([str(uid) for uid in set(finding_ids) if uid])

        # Construct payload string
        payload = (
            f"alerts:{','.join(sorted_alerts)}|"
            f"assets:{','.join(sorted_assets)}|"
            f"findings:{','.join(sorted_findings)}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
