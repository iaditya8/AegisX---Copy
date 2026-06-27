import uuid
from typing import List, Optional

from src.domain.entities.threat_intelligence import CampaignResponse
from src.services.campaign_registry import CampaignRegistry
from src.services.ioc_service import IOCService


class CampaignService:
    @classmethod
    def get_all_campaigns(cls, scope_id: Optional[uuid.UUID] = None) -> List[CampaignResponse]:
        """Retrieve all campaigns and their dynamically associated IOCs and threat actors."""
        profiles = CampaignRegistry.get_all_profiles()
        iocs = IOCService.get_all_iocs()

        if scope_id:
            iocs = [i for i in iocs if i.scope_id == scope_id]

        response = []
        for p in profiles:
            associated_iocs = [
                ioc.value
                for ioc in iocs
                if p.name in ioc.campaigns or any(alias in ioc.campaigns for alias in p.aliases)
            ]
            response.append(
                CampaignResponse(
                    campaign_id=p.campaign_id,
                    name=p.name,
                    description=p.description,
                    aliases=p.aliases,
                    severity=p.severity,
                    status=p.status,
                    iocs=associated_iocs,
                    threat_actors=p.threat_actors,
                )
            )
        return response

    @classmethod
    def get_campaign(
        cls, campaign_id: uuid.UUID, scope_id: Optional[uuid.UUID] = None
    ) -> Optional[CampaignResponse]:
        """Retrieve a specific campaign and its dynamically associated IOCs and threat actors."""
        profiles = CampaignRegistry.get_all_profiles()
        profile = next((p for p in profiles if p.campaign_id == campaign_id), None)
        if not profile:
            return None

        iocs = IOCService.get_all_iocs()
        if scope_id:
            iocs = [i for i in iocs if i.scope_id == scope_id]

        associated_iocs = [
            ioc.value
            for ioc in iocs
            if profile.name in ioc.campaigns or any(alias in ioc.campaigns for alias in profile.aliases)
        ]
        return CampaignResponse(
            campaign_id=profile.campaign_id,
            name=profile.name,
            description=profile.description,
            aliases=profile.aliases,
            severity=profile.severity,
            status=profile.status,
            iocs=associated_iocs,
            threat_actors=profile.threat_actors,
        )
