import uuid
from typing import Dict, Optional

from src.domain.entities.threat_intelligence import IOCStatus
from src.services.detection_coverage_service import DetectionCoverageService
from src.services.ioc_service import IOCService
from src.services.threat_actor_registry import ThreatActorRegistry
from src.services.campaign_registry import CampaignRegistry


class HuntCoverageService:
    @classmethod
    def calculate_coverage(cls, scope_id: Optional[uuid.UUID] = None) -> Dict[str, float]:
        """Compute hunting and threat intelligence coverage statistics."""
        # 1. Attack Coverage (from DetectionCoverageService)
        # Convert overall score (0.0 to 1.0) to percentage (0.0 to 100.0)
        overall_score = DetectionCoverageService.calculate_overall_score(scope_id)
        attack_coverage = overall_score * 100.0

        # 2. IOC Coverage
        iocs = IOCService.get_all_iocs()
        if scope_id:
            iocs = [i for i in iocs if i.scope_id == scope_id]

        total_iocs = len(iocs)
        active_iocs = len([i for i in iocs if i.status == IOCStatus.ACTIVE])
        ioc_coverage = (active_iocs / total_iocs * 100.0) if total_iocs > 0 else 100.0

        # 3. Threat Actor Coverage
        actors = ThreatActorRegistry.get_all_profiles()
        total_actors = len(actors)
        covered_actors = 0
        for actor in actors:
            # Check if any active IOC lists this actor
            has_active_ioc = any(
                ioc.status == IOCStatus.ACTIVE and actor.name in ioc.threat_actors
                for ioc in iocs
            )
            if has_active_ioc:
                covered_actors += 1

        actor_coverage = (covered_actors / total_actors * 100.0) if total_actors > 0 else 100.0

        # 4. Campaign Coverage
        campaigns = CampaignRegistry.get_all_profiles()
        total_campaigns = len(campaigns)
        covered_campaigns = 0
        for campaign in campaigns:
            # Check if any active IOC lists this campaign
            has_active_ioc = any(
                ioc.status == IOCStatus.ACTIVE and campaign.name in ioc.campaigns
                for ioc in iocs
            )
            if has_active_ioc:
                covered_campaigns += 1

        campaign_coverage = (covered_campaigns / total_campaigns * 100.0) if total_campaigns > 0 else 100.0

        return {
            "attack_coverage": round(attack_coverage, 2),
            "ioc_coverage": round(ioc_coverage, 2),
            "actor_coverage": round(actor_coverage, 2),
            "campaign_coverage": round(campaign_coverage, 2),
        }
