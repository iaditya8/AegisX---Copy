import hashlib
import uuid


class GraphFingerprintService:
    @classmethod
    def generate_node_fingerprint(cls, node_type: str, entity_id: uuid.UUID) -> str:
        """Generate stable SHA-256 fingerprint for a graph node."""
        raw = f"{node_type.strip().upper()}_{str(entity_id).strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def generate_edge_fingerprint(
        cls, source_id: uuid.UUID, edge_type: str, target_id: uuid.UUID
    ) -> str:
        """Generate stable SHA-256 fingerprint for a graph relationship/edge."""
        src = str(source_id).strip().lower()
        tgt = str(target_id).strip().lower()
        typ = edge_type.strip().upper()
        raw = f"{src}_{typ}_{tgt}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
