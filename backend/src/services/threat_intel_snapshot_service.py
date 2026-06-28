import uuid
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession


class ThreatIntelSnapshotService:
    # Cache store: scope_id -> Snapshot dictionary
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear the GRC threat intelligence snapshot cache."""
        cls._snapshots.clear()

    @classmethod
    def get_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Retrieve the cached GRC threat intelligence snapshot, defaulting to a minimal fallback if missing or corrupted."""
        snap = cls._snapshots.get(scope_id)
        if not snap or not isinstance(snap, dict) or "summary" not in snap:
            return {
                "summary": {
                    "total_threat_records": 0,
                    "active_threat_records": 0,
                    "archived_threat_records": 0,
                    "average_fusion_score": 0.0,
                },
                "records": {},
            }
        return snap

    @classmethod
    async def generate_snapshot(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None
    ) -> dict:
        """Dynamically rebuild GRC threat intelligence snapshot stats from active records."""
        from src.services.threat_intelligence_service import ThreatIntelligenceService
        from src.domain.entities.threat_intel import ThreatIntelStatus

        all_recs = ThreatIntelligenceService.get_all_threats()
        if scope_id:
            all_recs = [r for r in all_recs if r.scope_id == scope_id]

        total_recs = len(all_recs)
        active_count = sum(1 for r in all_recs if r.status in (ThreatIntelStatus.ACTIVE, ThreatIntelStatus.IN_TRIAGE, ThreatIntelStatus.FUSED))
        archived_count = sum(1 for r in all_recs if r.status == ThreatIntelStatus.ARCHIVED)

        avg_fusion = (
            round(sum(r.confidence or 0.0 for r in all_recs) / total_recs, 2)
            if total_recs > 0
            else 0.0
        )

        records_track = {}
        for r in all_recs:
            records_track[str(r.threat_intel_id)] = {
                "threat_intel_id": str(r.threat_intel_id),
                "value": r.value,
                "indicator_type": r.indicator_type.value,
                "status": r.status.value,
                "severity": r.severity.value,
                "confidence": r.confidence,
            }

        snapshot = {
            "summary": {
                "total_threat_records": total_recs,
                "active_threat_records": active_count,
                "archived_threat_records": archived_count,
                "average_fusion_score": avg_fusion,
            },
            "records": records_track,
        }

        cls._snapshots[scope_id] = snapshot
        return snapshot
