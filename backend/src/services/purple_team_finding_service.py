import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from src.domain.entities.purple_team import ExerciseSeverity, PurpleTeamFindingResponse


class PurpleTeamFindingService:
    # in-memory store: exercise_id -> list of PurpleTeamFindingResponse
    _findings: Dict[uuid.UUID, List[PurpleTeamFindingResponse]] = {}

    @classmethod
    def clear_findings(cls) -> None:
        """Clear all validation findings."""
        cls._findings.clear()

    @classmethod
    def get_findings(cls, exercise_id: uuid.UUID) -> List[PurpleTeamFindingResponse]:
        """Retrieve all validation findings for an exercise."""
        return cls._findings.get(exercise_id, [])

    @classmethod
    def get_all_findings(cls) -> List[PurpleTeamFindingResponse]:
        """Retrieve all validation findings in the system."""
        all_finds = []
        for finds in cls._findings.values():
            all_finds.extend(finds)
        return all_finds

    @classmethod
    def create_finding(
        cls,
        exercise_id: uuid.UUID,
        technique_id: str,
        severity: ExerciseSeverity,
        gap_type: str,
        description: str,
    ) -> PurpleTeamFindingResponse:
        """Create and store an append-only immutable validation finding."""
        # Check for duplicates (same exercise, technique, gap_type)
        existing = cls.get_findings(exercise_id)
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
        return finding
