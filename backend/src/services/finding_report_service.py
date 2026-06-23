import uuid
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Asset, Finding, Scope


class FindingReportService:
    """Service to generate filtered finding reports with RBAC scope ownership checks."""

    @classmethod
    async def generate_finding_report(
        cls,
        db: AsyncSession,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        template: Optional[str] = None,
        asset_id: Optional[uuid.UUID] = None,
        user_role: str = "admin",
        user_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Query findings on active assets using filters.

        Enforces scope ownership check for non-admin users.
        """
        q = select(Finding).join(Asset).where(Asset.deleted_at.is_(None))

        # Enforce RBAC ownership checks
        if user_role != "admin":
            if not user_id:
                return {"findings": [], "total_count": 0}
            q = q.join(Scope, Asset.scope_id == Scope.id).where(
                Scope.owner_id == user_id
            )

        if severity:
            q = q.where(Finding.severity == severity.lower())
        if status:
            q = q.where(Finding.status == status.lower())
        if template:
            q = q.where(Finding.template_id == template)
        if asset_id:
            q = q.where(Finding.asset_id == asset_id)

        # Count total
        count_q = select(func.count()).select_from(q.subquery())
        res_count = await db.execute(count_q)
        total = res_count.scalar() or 0

        # Sort findings by created_at desc
        q = q.order_by(Finding.created_at.desc())
        res = await db.execute(q)
        findings = res.scalars().all()

        findings_list = [
            {
                "id": str(f.id),
                "asset_id": str(f.asset_id),
                "title": f.title,
                "description": f.description,
                "severity": f.severity,
                "status": f.status,
                "template_id": f.template_id,
                "template_name": f.template_name,
                "source_plugin": f.source_plugin,
                "first_seen": f.first_seen.isoformat() if f.first_seen else None,
                "last_seen": f.last_seen.isoformat() if f.last_seen else None,
                "metadata_json": f.metadata_json,
            }
            for f in findings
        ]

        return {"findings": findings_list, "total_count": total}
