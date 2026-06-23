from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Finding


class TemplateTrackingService:
    """Service to track template findings, severity distribution, and
    affected assets.
    """

    @staticmethod
    async def get_template_stats(db: AsyncSession, template_id: str) -> Dict[str, Any]:
        """Aggregate stats for a single template."""
        # Query total count and template name
        q_count = select(
            func.count(Finding.id).label("total"),
            func.max(Finding.template_name).label("name"),
        ).where(Finding.template_id == template_id)
        res_count = await db.execute(q_count)
        row = res_count.one_or_none()

        if not row or row.total == 0:
            return {
                "template_id": template_id,
                "template_name": None,
                "finding_count": 0,
                "severity_distribution": {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                    "info": 0,
                },
                "affected_asset_count": 0,
            }

        # Query severity distribution
        q_dist = (
            select(Finding.severity, func.count(Finding.id))
            .where(Finding.template_id == template_id)
            .group_by(Finding.severity)
        )
        res_dist = await db.execute(q_dist)
        dist_rows = res_dist.all()

        distribution = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
        }
        for sev, count in dist_rows:
            if sev and sev.lower() in distribution:
                distribution[sev.lower()] = count

        # Count unique asset IDs for active findings
        q_assets = select(
            Finding.asset_id, Finding.metadata_json, Finding.status
        ).where(Finding.template_id == template_id)
        res_assets = await db.execute(q_assets)
        asset_rows = res_assets.all()

        affected_assets = set()
        for ar in asset_rows:
            meta = ar.metadata_json or {}
            # Active findings are: status in ("open", "acknowledged")
            # and closed_by_scan is False
            is_active = ar.status.lower() in ("open", "acknowledged")
            is_closed_by_scan = meta.get("closed_by_scan", False)
            if is_active and not is_closed_by_scan:
                affected_assets.add(ar.asset_id)

        affected_asset_count = len(affected_assets)

        return {
            "template_id": template_id,
            "template_name": row.name or template_id,
            "finding_count": row.total,
            "severity_distribution": distribution,
            "affected_asset_count": affected_asset_count,
        }

    @classmethod
    async def list_tracked_templates(cls, db: AsyncSession) -> List[Dict[str, Any]]:
        """List aggregates for all templates in the database."""
        q_templates = select(Finding.template_id).distinct()
        res_templates = await db.execute(q_templates)
        template_ids = res_templates.scalars().all()

        results = []
        for t_id in template_ids:
            stats = await cls.get_template_stats(db, t_id)
            results.append(stats)
        return results
