import hashlib
from typing import Optional


class RecommendationFingerprintService:
    @staticmethod
    def generate_fingerprint(
        asset_id: str,
        finding_id: Optional[str],
        recommendation_type: str,
        recommendation_title: str,
    ) -> str:
        """Generate a stable, deterministic recommendation fingerprint using SHA-256."""
        fid = finding_id or ""
        raw_str = (
            f"{asset_id}:{fid}:{recommendation_type.upper()}:{recommendation_title}"
        )
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
