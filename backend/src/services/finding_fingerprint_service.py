import hashlib
import uuid
from typing import Optional


class FindingFingerprintService:
    @staticmethod
    def generate_fingerprint(
        asset_id: uuid.UUID,
        template_id: str,
        matched_host: Optional[str] = None,
        matched_path: Optional[str] = None,
    ) -> str:
        """Generate a stable unique fingerprint using SHA256.

        Inputs: asset_id, template_id, and optional matched_host, matched_path.
        """
        parts = [str(asset_id), str(template_id)]
        if matched_host:
            parts.append(str(matched_host))
        if matched_path:
            parts.append(str(matched_path))

        raw_str = ":".join(parts)
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
