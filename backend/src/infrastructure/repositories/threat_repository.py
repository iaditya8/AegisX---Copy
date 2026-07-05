from typing import List, Optional
import uuid
from sqlalchemy.future import select
from src.core.tenant import get_current_tenant_id
from src.infrastructure.database.models import (
    ThreatIntelIOC,
    ThreatIntelActor,
    ThreatIntelCampaign,
    ThreatIntelIOCActorMapping,
    ThreatIntelIOCCampaignMapping,
    ThreatIntelActorCampaignMapping,
    ThreatIntelHistory,
)
from src.infrastructure.repositories.base import BaseRepository


class ThreatRepository(BaseRepository[ThreatIntelIOC]):
    def __init__(self, session):
        super().__init__(session, ThreatIntelIOC)

    async def get(self, id: uuid.UUID) -> Optional[ThreatIntelIOC]:
        result = await self.session.execute(
            select(ThreatIntelIOC).filter(
                ThreatIntelIOC.ioc_id == id,
                ThreatIntelIOC.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, id: uuid.UUID) -> Optional[ThreatIntelIOC]:
        return await self.get(id)

    async def get_by_fingerprint(self, fingerprint: str) -> Optional[ThreatIntelIOC]:
        result = await self.session.execute(
            select(ThreatIntelIOC).filter(
                ThreatIntelIOC.ioc_fingerprint == fingerprint,
                ThreatIntelIOC.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def list(self) -> List[ThreatIntelIOC]:
        result = await self.session.execute(
            select(ThreatIntelIOC).filter(ThreatIntelIOC.is_deleted == False)
        )
        return list(result.scalars().all())

    # Actor methods
    async def get_actor(self, actor_id: uuid.UUID) -> Optional[ThreatIntelActor]:
        result = await self.session.execute(
            select(ThreatIntelActor).filter(
                ThreatIntelActor.actor_id == actor_id,
                ThreatIntelActor.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def list_actors(self) -> List[ThreatIntelActor]:
        result = await self.session.execute(
            select(ThreatIntelActor).filter(ThreatIntelActor.is_deleted == False)
        )
        return list(result.scalars().all())

    async def save_actor(self, actor: ThreatIntelActor) -> None:
        self.session.add(actor)

    # Campaign methods
    async def get_campaign(self, campaign_id: uuid.UUID) -> Optional[ThreatIntelCampaign]:
        result = await self.session.execute(
            select(ThreatIntelCampaign).filter(
                ThreatIntelCampaign.campaign_id == campaign_id,
                ThreatIntelCampaign.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def list_campaigns(self) -> List[ThreatIntelCampaign]:
        result = await self.session.execute(
            select(ThreatIntelCampaign).filter(ThreatIntelCampaign.is_deleted == False)
        )
        return list(result.scalars().all())

    async def save_campaign(self, campaign: ThreatIntelCampaign) -> None:
        self.session.add(campaign)

    # Mapping methods
    async def link_ioc_to_actor(self, ioc_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        mapping = ThreatIntelIOCActorMapping(
            tenant_id=tenant_id,
            ioc_id=ioc_id,
            actor_id=actor_id
        )
        self.session.add(mapping)

    async def link_ioc_to_campaign(self, ioc_id: uuid.UUID, campaign_id: uuid.UUID) -> None:
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        mapping = ThreatIntelIOCCampaignMapping(
            tenant_id=tenant_id,
            ioc_id=ioc_id,
            campaign_id=campaign_id
        )
        self.session.add(mapping)

    async def link_actor_to_campaign(self, actor_id: uuid.UUID, campaign_id: uuid.UUID) -> None:
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        mapping = ThreatIntelActorCampaignMapping(
            tenant_id=tenant_id,
            actor_id=actor_id,
            campaign_id=campaign_id
        )
        self.session.add(mapping)

    # History methods
    async def get_history(self, ioc_id: uuid.UUID) -> List[ThreatIntelHistory]:
        result = await self.session.execute(
            select(ThreatIntelHistory)
            .filter_by(ioc_id=ioc_id)
            .order_by(ThreatIntelHistory.timestamp.desc())
        )
        return list(result.scalars().all())

    async def save_history(self, history_entry: ThreatIntelHistory) -> None:
        self.session.add(history_entry)
