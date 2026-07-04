from typing import List, Optional
import uuid
from sqlalchemy.future import select
from src.infrastructure.database.models import (
    GRCComplianceAssessment,
    GRCControl,
    GRCEvidence,
    GRCGap,
    GRCComplianceHistory,
)
from src.infrastructure.repositories.base import BaseRepository


class GRCRepository(BaseRepository[GRCComplianceAssessment]):
    def __init__(self, session):
        super().__init__(session, GRCComplianceAssessment)

    async def get_controls(self, assessment_id: uuid.UUID) -> List[GRCControl]:
        result = await self.session.execute(
            select(GRCControl).filter_by(assessment_id=assessment_id)
        )
        return list(result.scalars().all())

    async def save_control(self, control: GRCControl) -> None:
        self.session.add(control)

    async def get_evidence(self, assessment_id: uuid.UUID) -> List[GRCEvidence]:
        result = await self.session.execute(
            select(GRCEvidence).filter_by(assessment_id=assessment_id)
        )
        return list(result.scalars().all())

    async def save_evidence(self, evidence: GRCEvidence) -> None:
        self.session.add(evidence)

    async def get_gaps(self, assessment_id: uuid.UUID) -> List[GRCGap]:
        result = await self.session.execute(
            select(GRCGap).filter_by(assessment_id=assessment_id)
        )
        return list(result.scalars().all())

    async def save_gap(self, gap: GRCGap) -> None:
        self.session.add(gap)

    async def get_history(self, assessment_id: uuid.UUID) -> List[GRCComplianceHistory]:
        result = await self.session.execute(
            select(GRCComplianceHistory)
            .filter_by(assessment_id=assessment_id)
            .order_by(GRCComplianceHistory.timestamp.desc())
        )
        return list(result.scalars().all())

    async def save_history(self, history_entry: GRCComplianceHistory) -> None:
        self.session.add(history_entry)
