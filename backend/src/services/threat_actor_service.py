import uuid
from typing import List, Optional

from src.domain.entities.threat_intelligence import ThreatActorResponse
from src.services.ioc_service import IOCService
from src.services.threat_actor_registry import ThreatActorRegistry


class ThreatActorService:
    @classmethod
    def get_all_actors(cls, scope_id: Optional[uuid.UUID] = None) -> List[ThreatActorResponse]:
        """Retrieve all threat actors and their dynamically associated IOCs."""
        profiles = ThreatActorRegistry.get_all_profiles()
        iocs = IOCService.get_all_iocs()

        if scope_id:
            iocs = [i for i in iocs if i.scope_id == scope_id]

        response = []
        for p in profiles:
            associated_iocs = [
                ioc.value
                for ioc in iocs
                if p.name in ioc.threat_actors or any(alias in ioc.threat_actors for alias in p.aliases)
            ]
            response.append(
                ThreatActorResponse(
                    actor_id=p.actor_id,
                    name=p.name,
                    description=p.description,
                    aliases=p.aliases,
                    severity=p.severity,
                    status=p.status,
                    iocs=associated_iocs,
                )
            )
        return response

    @classmethod
    def get_actor(
        cls, actor_id: uuid.UUID, scope_id: Optional[uuid.UUID] = None
    ) -> Optional[ThreatActorResponse]:
        """Retrieve a specific threat actor and their dynamically associated IOCs."""
        profiles = ThreatActorRegistry.get_all_profiles()
        profile = next((p for p in profiles if p.actor_id == actor_id), None)
        if not profile:
            return None

        iocs = IOCService.get_all_iocs()
        if scope_id:
            iocs = [i for i in iocs if i.scope_id == scope_id]

        associated_iocs = [
            ioc.value
            for ioc in iocs
            if profile.name in ioc.threat_actors or any(alias in ioc.threat_actors for alias in profile.aliases)
        ]
        return ThreatActorResponse(
            actor_id=profile.actor_id,
            name=profile.name,
            description=profile.description,
            aliases=profile.aliases,
            severity=profile.severity,
            status=profile.status,
            iocs=associated_iocs,
        )
