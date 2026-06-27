import uuid
import copy
from typing import Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models import Finding
from src.services.exposure_service import ExposureService
from src.services.incident_service import IncidentService
from src.services.case_service import CaseService
from src.services.hunt_service import HuntService
from src.services.detection_service import DetectionService
from src.services.threat_actor_service import ThreatActorService
from src.services.campaign_service import CampaignService


class RiskCorrelationService:
    # in-memory store: posture_id -> list of correlations
    # Risk Correlation Preservation Rule: must never be deleted, modified, or overwritten.
    _correlations: Dict[uuid.UUID, List[dict]] = {}

    @classmethod
    def clear_correlations(cls) -> None:
        """Clear all posture correlations."""
        cls._correlations.clear()

    @classmethod
    def get_correlations(cls, posture_id: uuid.UUID) -> List[dict]:
        """Retrieve correlations for a posture."""
        return copy.deepcopy(cls._correlations.get(posture_id, []))

    @classmethod
    async def correlate_posture(
        cls, db: AsyncSession, posture_id: uuid.UUID, asset_id: uuid.UUID
    ) -> List[dict]:
        """Correlate posture against Findings, Exposures, Incidents, Cases, Hunts, Detections, campaigns, and actors."""
        # 1. Database Findings
        q_findings = select(Finding).where(Finding.asset_id == asset_id)
        findings = (await db.execute(q_findings)).scalars().all()

        # 2. Exposures
        exposures = [e for e in ExposureService.get_all_exposures() if e.asset_id == asset_id]

        # 3. Incidents
        incidents = [inc for inc in IncidentService.get_all_incidents() if asset_id in inc.asset_ids]

        # 4. Cases
        cases = [c for c in CaseService.get_all_cases() if asset_id in c.asset_ids]

        # 5. Hunts
        hunts = []
        for h in HuntService.get_all_hunts():
            for entity in h.related_entities:
                if str(entity.get("entity_id")) == str(asset_id):
                    hunts.append(h)
                    break

        # 6. Detections (active rules)
        detections = DetectionService.get_all_detections()

        # 7. Threat Actors & Campaigns
        actors = ThreatActorService.get_all_actors()
        campaigns = CampaignService.get_all_campaigns()

        # Build signatures to guarantee append-only uniqueness
        current = cls._correlations.setdefault(posture_id, [])
        existing_signatures = {f"{c['entity_type']}:{c['entity_id']}" for c in current}

        new_correlations = []

        for f in findings:
            sig = f"Finding:{str(f.id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Finding", "entity_id": str(f.id), "details": f.title})

        for e in exposures:
            sig = f"Exposure:{str(e.exposure_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Exposure", "entity_id": str(e.exposure_id), "details": e.title})

        for inc in incidents:
            sig = f"Incident:{str(inc.incident_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Incident", "entity_id": str(inc.incident_id), "details": inc.title})

        for c in cases:
            sig = f"Case:{str(c.case_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Case", "entity_id": str(c.case_id), "details": c.title})

        for h in hunts:
            sig = f"Hunt:{str(h.hunt_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Hunt", "entity_id": str(h.hunt_id), "details": h.title})

        for d in detections:
            sig = f"Detection:{str(d.detection_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Detection", "entity_id": str(d.detection_id), "details": d.name})

        for a in actors:
            sig = f"ThreatActor:{str(a.actor_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "ThreatActor", "entity_id": str(a.actor_id), "details": a.name})

        for camp in campaigns:
            sig = f"Campaign:{str(camp.campaign_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Campaign", "entity_id": str(camp.campaign_id), "details": camp.name})

        # Append new correlations
        current.extend(new_correlations)
        return current
