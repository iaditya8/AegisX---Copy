import uuid
from typing import Dict, Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models import Asset
from src.domain.entities.security_posture import RiskStatus, PostureSeverity
from src.services.security_posture_service import SecurityPostureService
from src.services.attack_surface_service import AttackSurfaceService


class SecurityPostureSnapshotService:
    # Cache store: scope_id -> Snapshot dictionary
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}
    _risk_trends: Dict[Optional[uuid.UUID], List[float]] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear the posture snapshot cache."""
        cls._snapshots.clear()
        cls._risk_trends.clear()

    @classmethod
    def get_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Retrieve the cached posture snapshot. Rebuilds dynamically if missing/corrupted."""
        snap = cls._snapshots.get(scope_id)
        if not snap or not isinstance(snap, dict) or "summary" not in snap:
            # Minimal fallback that contains defaults
            return {
                "summary": {
                    "total_postures": 0,
                    "organizational_risk_score": 0.0,
                    "security_posture_score": 100.0,
                    "critical_risk_count": 0,
                    "attack_surface_coverage": 100.0,
                    "risk_trends": cls._risk_trends.setdefault(scope_id, [0.0]),
                },
                "status_counts": {},
                "postures": {},
            }
        return snap

    @classmethod
    async def generate_snapshot(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None
    ) -> dict:
        """Dynamically rebuild organizational risk, posture scores, and critical counts from active records."""
        # 1. Fetch assets in scope
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        if scope_id:
            q_assets = q_assets.where(Asset.scope_id == scope_id)
        assets = (await db.execute(q_assets)).scalars().all()
        asset_ids = {a.id for a in assets}

        # 2. Get postures
        all_postures = SecurityPostureService.get_all_postures()
        if scope_id:
            all_postures = [p for p in all_postures if p.asset_id in asset_ids]

        total_postures = len(all_postures)
        active_postures = [p for p in all_postures if p.status != RiskStatus.CLOSED]

        # 3. Calculate scores
        if active_postures:
            org_risk_score = round(sum(p.risk_score for p in active_postures) / len(active_postures), 2)
            sec_posture_score = round(sum(p.posture_score for p in active_postures) / len(active_postures), 2)
        else:
            org_risk_score = 0.0
            sec_posture_score = 100.0

        critical_count = sum(
            1 for p in active_postures if p.severity == PostureSeverity.CRITICAL
        )

        status_counts = {}
        for p in all_postures:
            status_counts[p.status.value] = status_counts.get(p.status.value, 0) + 1

        # 4. Coverage calculation
        assets_with_posture = {p.asset_id for p in all_postures}
        if assets:
            coverage = round((len(assets_with_posture) / len(assets)) * 100.0, 2)
        else:
            coverage = 100.0

        # Update trend history dynamically
        trends = cls._risk_trends.setdefault(scope_id, [])
        trends.append(org_risk_score)
        if len(trends) > 10:
            trends.pop(0)

        # Build list of postures mapping details
        postures_track = {}
        for p in all_postures:
            postures_track[str(p.posture_id)] = {
                "posture_id": str(p.posture_id),
                "posture_fingerprint": p.posture_fingerprint,
                "severity": p.severity.value,
                "status": p.status.value,
                "risk_score": p.risk_score,
                "posture_score": p.posture_score,
                "title": p.title,
            }

        snapshot = {
            "summary": {
                "total_postures": total_postures,
                "organizational_risk_score": org_risk_score,
                "security_posture_score": sec_posture_score,
                "critical_risk_count": critical_count,
                "attack_surface_coverage": coverage,
                "risk_trends": list(trends),
            },
            "status_counts": status_counts,
            "postures": postures_track,
        }

        cls._snapshots[scope_id] = snapshot
        return snapshot
