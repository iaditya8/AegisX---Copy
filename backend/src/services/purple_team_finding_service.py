import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from src.domain.entities.purple_team import ExerciseSeverity, PurpleTeamFindingResponse
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import PurpleTeamFinding
from src.core.tenant import get_current_tenant_id


class PurpleTeamFindingService:
    # in-memory store: exercise_id -> list of PurpleTeamFindingResponse
    _findings: Dict[uuid.UUID, List[PurpleTeamFindingResponse]] = {}

    @classmethod
    def clear_findings(cls) -> None:
        """Clear all validation findings."""
        cls._findings.clear()

    @classmethod
    async def get_findings(cls, exercise_id: uuid.UUID) -> List[PurpleTeamFindingResponse]:
        """Retrieve all validation findings for an exercise."""
        async with UnitOfWork() as uow:
            db_findings = await uow.purple_team_repo.list_findings(exercise_id)
            return [
                PurpleTeamFindingResponse(
                    finding_id=f.finding_id,
                    exercise_id=f.exercise_id,
                    technique_id=f.technique_id,
                    severity=ExerciseSeverity(f.severity),
                    gap_type=f.gap_type,
                    description=f.description,
                    created_at=f.created_at,
                )
                for f in db_findings
            ]

    @classmethod
    async def get_all_findings(cls) -> List[PurpleTeamFindingResponse]:
        """Retrieve all validation findings in the system."""
        async with UnitOfWork() as uow:
            from sqlalchemy.future import select
            result = await uow.session.execute(select(PurpleTeamFinding))
            db_findings = list(result.scalars().all())
            return [
                PurpleTeamFindingResponse(
                    finding_id=f.finding_id,
                    exercise_id=f.exercise_id,
                    technique_id=f.technique_id,
                    severity=ExerciseSeverity(f.severity),
                    gap_type=f.gap_type,
                    description=f.description,
                    created_at=f.created_at,
                )
                for f in db_findings
            ]

    @classmethod
    async def create_finding(
        cls,
        exercise_id: uuid.UUID,
        technique_id: str,
        severity: ExerciseSeverity,
        gap_type: str,
        description: str,
    ) -> PurpleTeamFindingResponse:
        """Create and store an append-only immutable validation finding."""
        # Check for duplicates (same exercise, technique, gap_type)
        existing = await cls.get_findings(exercise_id)
        for f in existing:
            if f.technique_id == technique_id and f.gap_type == gap_type:
                return f

        finding_id = uuid.uuid4()
        finding = PurpleTeamFindingResponse(
            finding_id=finding_id,
            exercise_id=exercise_id,
            technique_id=technique_id,
            severity=severity,
            gap_type=gap_type,
            description=description,
            created_at=datetime.now(timezone.utc),
        )
        cls._findings.setdefault(exercise_id, []).append(finding)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_f = PurpleTeamFinding(
                tenant_id=tenant_id,
                finding_id=finding_id,
                exercise_id=exercise_id,
                technique_id=technique_id,
                severity=severity.value,
                gap_type=gap_type,
                description=description,
                created_at=finding.created_at,
            )
            await uow.purple_team_repo.save_finding(db_f)
            await uow.commit()

        return finding
