import hashlib


class ResilienceFingerprintService:
    @classmethod
    def generate_fingerprint(
        cls,
        title: str,
        service_name: str,
        service_criticality: str,
    ) -> str:
        """Generate stable report fingerprint using SHA-256(title:service_name:service_criticality)."""
        normalized_title = str(title).strip().lower()
        normalized_service = str(service_name).strip().lower()
        normalized_criticality = str(service_criticality).strip().lower()

        payload = f"title:{normalized_title}|service:{normalized_service}|criticality:{normalized_criticality}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
