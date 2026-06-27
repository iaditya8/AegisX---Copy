import uuid
from typing import Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.exposure_service import ExposureService
from src.services.attack_surface_service import AttackSurfaceService
from src.services.workflow_event_service import WorkflowEventService


class ExposureDriftService:
    @classmethod
    async def check_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Detect and alert on exposure drifts, severity updates, prioritization regressions, or attack surface changes."""
        if not prev_snapshot:
            return

        # 1. Fetch current exposures
        exposures = ExposureService.get_all_exposures()
        if scope_id:
            # Filter exposures by asset scope
            from sqlalchemy import select
            from src.infrastructure.database.models import Asset
            q_assets = select(Asset.id).where(Asset.scope_id == scope_id, Asset.deleted_at.is_(None))
            res = await db.execute(q_assets)
            scoped_asset_ids = set(res.scalars().all())
            exposures = [e for e in exposures if e.asset_id in scoped_asset_ids]

        curr_exp_dict = {str(e.exposure_id): e for e in exposures}
        prev_exp_dict = prev_snapshot.get("exposures", {})

        # NEW_EXPOSURE & SEVERITY_CHANGED & PRIORITY_CHANGED
        for eid, curr in curr_exp_dict.items():
            prev = prev_exp_dict.get(eid)
            if not prev:
                # Also check fingerprint fallback in case of sync rebuilds
                fp_match = False
                for peid, pe in prev_exp_dict.items():
                    if pe.get("exposure_fingerprint") == curr.exposure_fingerprint:
                        fp_match = True
                        prev = pe
                        break
                if not fp_match:
                    await WorkflowEventService.emit_event(
                        db=db,
                        event_type="exposure.drift",
                        payload={
                            "drift_type": "NEW_EXPOSURE",
                            "exposure_id": str(curr.exposure_id),
                            "title": curr.title,
                            "severity": curr.severity.value,
                            "risk_score": curr.risk_score,
                        },
                    )
                    continue

            # Check severity changes
            if prev.get("severity") != curr.severity.value:
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="exposure.drift",
                    payload={
                        "drift_type": "SEVERITY_CHANGED",
                        "exposure_id": str(curr.exposure_id),
                        "previous_severity": prev.get("severity"),
                        "current_severity": curr.severity.value,
                    },
                )

            # Check priority/risk score changes
            if prev.get("risk_score") != curr.risk_score:
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="exposure.priority_changed",
                    payload={
                        "drift_type": "PRIORITY_CHANGED",
                        "exposure_id": str(curr.exposure_id),
                        "previous_risk_score": prev.get("risk_score"),
                        "current_risk_score": curr.risk_score,
                    },
                )

        # EXPOSURE_REMOVED
        for peid, prev in prev_exp_dict.items():
            # If prev not in current
            if peid not in curr_exp_dict:
                fp_match = False
                for curr in curr_exp_dict.values():
                    if curr.exposure_fingerprint == prev.get("exposure_fingerprint"):
                        fp_match = True
                        break
                if not fp_match:
                    await WorkflowEventService.emit_event(
                        db=db,
                        event_type="exposure.drift",
                        payload={
                            "drift_type": "EXPOSURE_REMOVED",
                            "exposure_id": peid,
                            "title": prev.get("title"),
                        },
                    )

        # 2. Check Attack Surface changes
        prev_attack_surface = prev_snapshot.get("attack_surface", {})
        # Query current attack surface categories for each asset in scope
        from sqlalchemy import select
        from src.infrastructure.database.models import Asset
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        if scope_id:
            q_assets = q_assets.where(Asset.scope_id == scope_id)
        assets = (await db.execute(q_assets)).scalars().all()

        for asset in assets:
            curr_cats = sorted(list(await AttackSurfaceService.get_asset_categories(db, asset.id)))
            prev_cats = prev_attack_surface.get(str(asset.id), [])
            if curr_cats != prev_cats:
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="exposure.drift",
                    payload={
                        "drift_type": "ATTACK_SURFACE_CHANGED",
                        "asset_id": str(asset.id),
                        "previous_categories": prev_cats,
                        "current_categories": curr_cats,
                    },
                )
