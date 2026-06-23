from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Finding, FindingHistory
from src.services.risk_history_service import RiskHistoryService


class DashboardTrendService:
    """Service to generate time-series trend metrics for dashboard visualization."""

    @classmethod
    async def generate_trends(cls, db: AsyncSession, days: int = 30) -> Dict[str, Any]:
        """Generate time-series trends for platform risk and open findings counts inside a window."""
        if days not in [7, 30, 90, 365]:
            raise ValueError("Invalid trend window days")

        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)

        # 1. Compile platform-wide risk trend from RiskHistoryService filtered by cutoff
        all_risk_entries = []
        for asset_id, entries in RiskHistoryService._history.items():
            for entry in entries:
                ts_str = entry.get("timestamp", "")
                if ts_str:
                    try:
                        entry_dt = datetime.fromisoformat(ts_str)
                        if entry_dt.tzinfo is None:
                            entry_dt = entry_dt.replace(tzinfo=timezone.utc)
                        else:
                            entry_dt = entry_dt.astimezone(timezone.utc)

                        if entry_dt >= cutoff_dt:
                            all_risk_entries.append(
                                {
                                    "asset_id": str(asset_id),
                                    "risk_score": entry.get("risk_score", 0),
                                    "timestamp": ts_str,
                                }
                            )
                    except ValueError:
                        pass

        # Sort chronologically
        all_risk_entries = sorted(all_risk_entries, key=lambda x: x["timestamp"])

        risk_trend: List[Dict[str, Any]] = []
        running_scores: Dict[str, float] = {}

        for entry in all_risk_entries:
            running_scores[entry["asset_id"]] = float(entry["risk_score"])
            avg_score = sum(running_scores.values()) / len(running_scores)
            risk_trend.append(
                {"timestamp": entry["timestamp"], "value": float(avg_score)}
            )

        # 2. Compile finding and critical finding trends from FindingHistory filtered by cutoff
        q_finding_history = (
            select(FindingHistory, Finding.severity)
            .join(Finding)
            .where(FindingHistory.created_at >= cutoff_dt)
            .order_by(FindingHistory.created_at.asc())
        )
        res_fh = await db.execute(q_finding_history)
        history_rows = res_fh.all()

        finding_trend: List[Dict[str, Any]] = []
        critical_finding_trend: List[Dict[str, Any]] = []

        running_findings = 0
        running_critical = 0

        for hist, severity in history_rows:
            ts = hist.created_at.isoformat()
            sev = str(severity).lower()

            change = 0
            if hist.change_type == "create":
                change = 1
            elif hist.change_type == "status_change":
                old_status = (hist.old_value or {}).get("status", "").lower()
                new_status = (hist.new_value or {}).get("status", "").lower()

                was_active = old_status in ["open", "acknowledged"] or not old_status
                is_active = new_status in ["open", "acknowledged"]

                # If it transitioned status
                if was_active and not is_active:
                    change = -1
                elif not was_active and is_active:
                    change = 1

            if change != 0:
                running_findings += change
                finding_trend.append(
                    {"timestamp": ts, "value": float(running_findings)}
                )

                if sev == "critical":
                    running_critical += change
                    critical_finding_trend.append(
                        {"timestamp": ts, "value": float(running_critical)}
                    )

        return {
            "risk_trend": risk_trend,
            "finding_trend": finding_trend,
            "critical_finding_trend": critical_finding_trend,
        }
