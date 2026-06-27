import uuid
from typing import Dict, List, Optional

from src.domain.entities.threat_intelligence import CampaignStatus, IOCSeverity


class CampaignProfile:
    def __init__(
        self,
        campaign_id: uuid.UUID,
        name: str,
        description: str,
        aliases: List[str],
        severity: IOCSeverity,
        status: CampaignStatus,
        threat_actors: List[str],
    ):
        self.campaign_id = campaign_id
        self.name = name
        self.description = description
        self.aliases = aliases or []
        self.severity = severity
        self.status = status
        self.threat_actors = threat_actors or []


class CampaignRegistry:
    # Pre-seeded campaigns
    _campaigns: Dict[str, CampaignProfile] = {
        "Operation Ghost": CampaignProfile(
            campaign_id=uuid.UUID("a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1"),
            name="Operation Ghost",
            description="Campaign targeting government agencies globally.",
            aliases=["Ghost Campaign"],
            severity=IOCSeverity.CRITICAL,
            status=CampaignStatus.ACTIVE,
            threat_actors=["APT29"],
        ),
        "Operation Grizzly": CampaignProfile(
            campaign_id=uuid.UUID("b2b2b2b2-b2b2-b2b2-b2b2-b2b2b2b2b2b2"),
            name="Operation Grizzly",
            description="Widespread campaign targeting political organizations.",
            aliases=["Grizzly Steppe"],
            severity=IOCSeverity.HIGH,
            status=CampaignStatus.ACTIVE,
            threat_actors=["APT28"],
        ),
    }

    @classmethod
    def get_campaign_by_name(cls, name: str) -> Optional[CampaignProfile]:
        """Case-insensitive or alias lookup for a campaign profile."""
        name_upper = name.upper()
        for k, v in cls._campaigns.items():
            if k.upper() == name_upper or name_upper in [a.upper() for a in v.aliases]:
                return v
        return None

    @classmethod
    def get_all_profiles(cls) -> List[CampaignProfile]:
        """Retrieve all pre-seeded campaign profiles."""
        return list(cls._campaigns.values())
