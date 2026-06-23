import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Asset, Finding, FindingHistory, ScanRun


def _make_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class FindingSnapshotService:
    """Service to aggregate finding statistics (snapshots) per asset."""

    _snapshots: Dict[uuid.UUID, Dict[str, Any]] = {}

    @classmethod
    async def count_new_findings_since(
        cls, db: AsyncSession, asset_id: uuid.UUID, timestamp: datetime
    ) -> int:
        """Count newly created findings for this asset since the timestamp."""
        timestamp_utc = _make_utc(timestamp)
        q = (
            select(func.count(FindingHistory.id))
            .join(Finding)
            .where(
                Finding.asset_id == asset_id,
                FindingHistory.change_type == "create",
                FindingHistory.created_at >= timestamp_utc,
            )
        )
        res = await db.execute(q)
        return res.scalar_one_or_none() or 0

    @classmethod
    async def count_resolved_since(
        cls, db: AsyncSession, asset_id: uuid.UUID, timestamp: datetime
    ) -> int:
        """Count findings transitioned to resolved for this asset since the
        timestamp.
        """
        timestamp_utc = _make_utc(timestamp)
        q = (
            select(FindingHistory)
            .join(Finding)
            .where(
                Finding.asset_id == asset_id,
                FindingHistory.change_type == "status_change",
                FindingHistory.created_at >= timestamp_utc,
            )
        )
        res = await db.execute(q)
        histories = res.scalars().all()
        return sum(
            1
            for h in histories
            if h.new_value and h.new_value.get("status") == "resolved"
        )

    @classmethod
    async def count_reopened_since(
        cls, db: AsyncSession, asset_id: uuid.UUID, timestamp: datetime
    ) -> int:
        """Count resolved findings rediscovered for this asset since the
        timestamp.
        """
        timestamp_utc = _make_utc(timestamp)
        q = (
            select(FindingHistory)
            .join(Finding)
            .where(
                Finding.asset_id == asset_id,
                FindingHistory.change_type == "status_change",
                FindingHistory.created_at >= timestamp_utc,
            )
        )
        res = await db.execute(q)
        histories = res.scalars().all()
        return sum(
            1
            for h in histories
            if h.old_value
            and h.old_value.get("status") == "resolved"
            and h.new_value
            and h.new_value.get("status") == "open"
        )

    @classmethod
    async def generate_finding_snapshot(
        cls,
        db: AsyncSession,
        asset_id: uuid.UUID,
        since_timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Aggregate finding counts, scan timestamps, and trend metrics for a
        specific asset.
        """
        q = select(Finding).where(Finding.asset_id == asset_id)
        res = await db.execute(q)
        findings = res.scalars().all()

        counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
            "open": 0,
            "acknowledged": 0,
            "resolved": 0,
            "suppressed": 0,
        }

        last_scan = None

        for f in findings:
            sev = f.severity.lower()
            if sev in counts:
                counts[sev] += 1

            status = f.status.lower()
            if status in counts:
                counts[status] += 1

            # Determine the latest scan timestamp
            if f.last_seen:
                f_last_seen_utc = _make_utc(f.last_seen)
                if last_scan is None or f_last_seen_utc > last_scan:
                    last_scan = f_last_seen_utc

        # Determine timestamp for trend metrics if not explicitly passed
        if since_timestamp is None:
            # Look up the scope of the asset to get the latest scan run
            asset = await db.get(Asset, asset_id)
            if asset:
                q_sr = (
                    select(ScanRun)
                    .where(
                        ScanRun.scope_id == asset.scope_id,
                        ScanRun.status.in_(["running", "completed"]),
                    )
                    .order_by(ScanRun.start_ts.desc())
                    .limit(1)
                )
                res_sr = await db.execute(q_sr)
                sr = res_sr.scalar_one_or_none()
                if sr and sr.start_ts:
                    since_timestamp = sr.start_ts

        if since_timestamp is None:
            since_timestamp = datetime(1970, 1, 1, tzinfo=timezone.utc)

        since_timestamp_utc = _make_utc(since_timestamp)

        # Derive trend metrics from FindingHistory records
        new_cnt = await cls.count_new_findings_since(db, asset_id, since_timestamp_utc)
        res_cnt = await cls.count_resolved_since(db, asset_id, since_timestamp_utc)
        reop_cnt = await cls.count_reopened_since(db, asset_id, since_timestamp_utc)

        snapshot = {
            "asset_id": str(asset_id),
            "critical_count": counts["critical"],
            "high_count": counts["high"],
            "medium_count": counts["medium"],
            "low_count": counts["low"],
            "info_count": counts["info"],
            "open_count": counts["open"],
            "acknowledged_count": counts["acknowledged"],
            "resolved_count": counts["resolved"],
            "suppressed_count": counts["suppressed"],
            "new_findings_since_last_scan": new_cnt,
            "resolved_since_last_scan": res_cnt,
            "reopened_since_last_scan": reop_cnt,
            "last_scan": last_scan.isoformat() if last_scan else None,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        return snapshot

    @classmethod
    async def update_finding_snapshot(
        cls,
        db: AsyncSession,
        asset_id: uuid.UUID,
        since_timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Recompute and save the snapshot for a specific asset."""
        snapshot = await cls.generate_finding_snapshot(db, asset_id, since_timestamp)
        cls._snapshots[asset_id] = snapshot
        return snapshot

    @classmethod
    def get_finding_snapshot(cls, asset_id: uuid.UUID) -> Dict[str, Any]:
        """Retrieve the latest snapshot from memory storage."""
        return cls._snapshots.get(
            asset_id,
            {
                "asset_id": str(asset_id),
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
                "info_count": 0,
                "open_count": 0,
                "acknowledged_count": 0,
                "resolved_count": 0,
                "suppressed_count": 0,
                "new_findings_since_last_scan": 0,
                "resolved_since_last_scan": 0,
                "reopened_since_last_scan": 0,
                "last_scan": None,
                "last_updated": None,
            },
        )
