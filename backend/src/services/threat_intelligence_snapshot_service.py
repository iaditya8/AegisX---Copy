import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from src.services.ioc_service import IOCService


class ThreatIntelligenceSnapshotService:
    # Cache-only store: scope_id (Optional[uuid.UUID]) -> snapshot dict
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear all cached snapshots."""
        cls._snapshots.clear()

    @classmethod
    def generate_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Generate a new snapshot dynamically from active threat intelligence records."""
        iocs = IOCService.get_all_iocs()
        if scope_id:
            iocs = [i for i in iocs if i.scope_id == scope_id]

        active_iocs = [i for i in iocs if i.status.value == "ACTIVE"]

        total_iocs = len(iocs)
        total_active = len(active_iocs)
        avg_reputation = sum(i.reputation for i in active_iocs) / total_active if total_active > 0 else 0.0

        snapshot = {
            "summary": {
                "total_iocs": total_iocs,
                "active_iocs": total_active,
                "average_reputation": avg_reputation,
            },
            "iocs": {
                str(ioc.ioc_id): {
                    "value": ioc.value,
                    "ioc_type": ioc.ioc_type.value,
                    "severity": ioc.severity.value,
                    "status": ioc.status.value,
                    "reputation": ioc.reputation,
                    "threat_actors": ioc.threat_actors,
                    "campaigns": ioc.campaigns,
                }
                for ioc in iocs
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        cls._snapshots[scope_id] = snapshot
        return snapshot

    @classmethod
    def get_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Get the cached snapshot, rebuilding dynamically if missing (cache-only consistency)."""
        if scope_id not in cls._snapshots or cls._snapshots[scope_id] is None:
            return cls.generate_snapshot(scope_id)
        return cls._snapshots[scope_id]
