import uuid
from typing import List, Optional
from sqlalchemy.future import select
from src.infrastructure.repositories.base import BaseRepository
from src.infrastructure.database.models import Incident, IncidentInvestigation, IncidentHistory, IncidentEvidence

class IncidentRepository(BaseRepository[Incident]):
    def __init__(self, session):
        super().__init__(session, Incident)

    async def get(self, id: uuid.UUID) -> Optional[Incident]:
        result = await self.session.execute(
            select(Incident).filter(Incident.id == id, Incident.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list(self) -> List[Incident]:
        result = await self.session.execute(
            select(Incident).filter(Incident.is_deleted == False)
        )
        return list(result.scalars().all())

    async def get_by_fingerprint(self, fingerprint: str) -> Optional[Incident]:
        result = await self.session.execute(
            select(Incident).filter(
                Incident.incident_fingerprint == fingerprint,
                Incident.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def save_investigation(self, entry: IncidentInvestigation) -> None:
        self.session.add(entry)

    async def list_investigations(self, incident_id: uuid.UUID) -> List[IncidentInvestigation]:
        result = await self.session.execute(
            select(IncidentInvestigation).filter(IncidentInvestigation.incident_id == incident_id)
        )
        return list(result.scalars().all())

    async def save_history(self, entry: IncidentHistory) -> None:
        self.session.add(entry)

    async def list_history(self, incident_id: uuid.UUID) -> List[IncidentHistory]:
        result = await self.session.execute(
            select(IncidentHistory).filter(IncidentHistory.incident_id == incident_id)
        )
        return list(result.scalars().all())

    async def save_evidence(self, entry: IncidentEvidence) -> None:
        self.session.add(entry)

    async def list_evidence(self, incident_id: uuid.UUID) -> List[IncidentEvidence]:
        result = await self.session.execute(
            select(IncidentEvidence).filter(IncidentEvidence.incident_id == incident_id)
        )
        return list(result.scalars().all())
