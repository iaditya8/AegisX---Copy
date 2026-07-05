from typing import List, Optional
import uuid
from sqlalchemy.future import select
from src.infrastructure.database.models import (
    GRCAssessment,
    GRCFrameworkControl,
    GRCEvidence,
    GRCGap,
    GRCHistory,
)
from src.infrastructure.repositories.base import BaseRepository


class GRCRepository(BaseRepository[GRCAssessment]):
    def __init__(self, session):
        super().__init__(session, GRCAssessment)

    async def get_by_id(self, id: uuid.UUID) -> Optional[GRCAssessment]:
        result = await self.session.execute(
            select(GRCAssessment).filter(
                GRCAssessment.id == id,
                GRCAssessment.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def get_by_fingerprint(self, tenant_id: uuid.UUID, fingerprint: str) -> Optional[GRCAssessment]:
        result = await self.session.execute(
            select(GRCAssessment).filter(
                GRCAssessment.tenant_id == tenant_id,
                GRCAssessment.assessment_fingerprint == fingerprint,
                GRCAssessment.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def get_active_assessments(self, tenant_id: uuid.UUID) -> List[GRCAssessment]:
        result = await self.session.execute(
            select(GRCAssessment).filter(
                GRCAssessment.tenant_id == tenant_id,
                GRCAssessment.status == "ACTIVE",
                GRCAssessment.is_deleted == False
            )
        )
        return list(result.scalars().all())

    async def get_controls(self, assessment_id: uuid.UUID) -> List[GRCFrameworkControl]:
        result = await self.session.execute(
            select(GRCFrameworkControl).filter(
                GRCFrameworkControl.is_deleted == False
            )
        )
        return list(result.scalars().all())

    async def save_control(self, control: GRCFrameworkControl) -> None:
        self.session.add(control)

    async def get_evidence(self, assessment_id: uuid.UUID) -> List[GRCEvidence]:
        result = await self.session.execute(
            select(GRCEvidence).filter(
                GRCEvidence.assessment_id == assessment_id,
                GRCEvidence.is_deleted == False
            )
        )
        return list(result.scalars().all())

    async def save_evidence(self, evidence: GRCEvidence) -> None:
        self.session.add(evidence)

    async def get_gaps(self, assessment_id: uuid.UUID) -> List[GRCGap]:
        result = await self.session.execute(
            select(GRCGap).filter(
                GRCGap.assessment_id == assessment_id,
                GRCGap.is_deleted == False
            )
        )
        return list(result.scalars().all())

    async def get_open_compliance_gaps(self, tenant_id: uuid.UUID) -> List[GRCGap]:
        result = await self.session.execute(
            select(GRCGap)
            .join(GRCAssessment, GRCGap.assessment_id == GRCAssessment.id)
            .filter(
                GRCAssessment.tenant_id == tenant_id,
                GRCGap.is_deleted == False,
                GRCAssessment.is_deleted == False
            )
        )
        return list(result.scalars().all())

    async def save_gap(self, gap: GRCGap) -> None:
        self.session.add(gap)

    async def get_history(self, assessment_id: uuid.UUID) -> List[GRCHistory]:
        result = await self.session.execute(
            select(GRCHistory)
            .filter(
                GRCHistory.assessment_id == assessment_id,
                GRCHistory.is_deleted == False
            )
            .order_by(GRCHistory.timestamp.desc())
        )
        return list(result.scalars().all())

    async def save_history(self, history_entry: GRCHistory) -> None:
        self.session.add(history_entry)
