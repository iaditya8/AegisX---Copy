import uuid
from typing import Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models import Finding
from src.services.alert_lifecycle_service import AlertLifecycleService
from src.services.incident_service import IncidentService
from src.services.case_service import CaseService
from src.services.hunt_service import HuntService
from src.services.purple_team_finding_service import PurpleTeamFindingService
from src.services.purple_team_service import PurpleTeamService


class ExposureCorrelationService:
    # in-memory store: exposure_id -> list of correlated entities
    _correlations: Dict[uuid.UUID, List[dict]] = {}

    @classmethod
    def clear_correlations(cls) -> None:
        """Clear all correlated exposures."""
        cls._correlations.clear()

    @classmethod
    def get_correlations(cls, exposure_id: uuid.UUID) -> List[dict]:
        """Retrieve all correlations for an exposure."""
        return cls._correlations.get(exposure_id, [])

    @classmethod
    async def correlate_exposure(
        cls, db: AsyncSession, exposure_id: uuid.UUID, asset_id: uuid.UUID
    ) -> List[dict]:
        """Correlate exposure against Findings, Risks, Alerts, Incidents, Cases, Hunts, and Purple Team findings."""
        # 1. Fetch Findings from database
        q_findings = select(Finding).where(Finding.asset_id == asset_id)
        findings = (await db.execute(q_findings)).scalars().all()

        # 2. Fetch Alerts
        alerts = AlertLifecycleService.get_all_alerts()
        asset_alerts = [a for a in alerts if a.asset_id == asset_id]

        # 3. Fetch Incidents
        incidents = IncidentService.get_all_incidents()
        asset_incidents = [inc for inc in incidents if asset_id in inc.asset_ids]

        # 4. Fetch Cases
        cases = CaseService.get_all_cases()
        asset_cases = [c for c in cases if asset_id in c.asset_ids]

        # 5. Fetch Hunts
        hunts = HuntService.get_all_hunts()
        asset_hunts = []
        for h in hunts:
            # Check if asset_id is in related_entities
            for entity in h.related_entities:
                if str(entity.get("entity_id")) == str(asset_id):
                    asset_hunts.append(h)
                    break

        # 6. Fetch Purple Team exercises/findings
        exercises = PurpleTeamService.get_all_exercises()
        asset_pt_findings = []
        for ex in exercises:
            # Check if asset_id is in related_entities
            has_asset = False
            for entity in ex.related_entities:
                if str(entity.get("entity_id")) == str(asset_id):
                    has_asset = True
                    break
            if has_asset:
                # Add findings for this exercise
                asset_pt_findings.extend(PurpleTeamFindingService.get_findings(ex.exercise_id))

        # Convert to correlation dicts
        current = cls._correlations.setdefault(exposure_id, [])
        existing_signatures = {f"{c['entity_type']}:{c['entity_id']}" for c in current}

        new_correlations = []

        for f in findings:
            sig = f"Finding:{str(f.id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Finding", "entity_id": str(f.id), "details": f.title})

        for a in asset_alerts:
            sig = f"Alert:{str(a.alert_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Alert", "entity_id": str(a.alert_id), "details": a.title})

        for inc in asset_incidents:
            sig = f"Incident:{str(inc.incident_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Incident", "entity_id": str(inc.incident_id), "details": inc.title})

        for c in asset_cases:
            sig = f"Case:{str(c.case_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Case", "entity_id": str(c.case_id), "details": c.title})

        for h in asset_hunts:
            sig = f"Hunt:{str(h.hunt_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Hunt", "entity_id": str(h.hunt_id), "details": h.title})

        for ptf in asset_pt_findings:
            sig = f"PurpleTeamFinding:{str(ptf.finding_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "PurpleTeamFinding", "entity_id": str(ptf.finding_id), "details": ptf.description})

        # Append new correlations (Correlation Preservation Rule: immutable and append-only)
        current.extend(new_correlations)
        return current
