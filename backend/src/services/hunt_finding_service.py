import uuid
from datetime import datetime, timezone
from typing import Dict, List

from src.domain.entities.hunt import HuntFindingResponse


class HuntFindingService:
    # in-memory store: hunt_id -> list of findings
    _findings: Dict[uuid.UUID, List[HuntFindingResponse]] = {}

    @classmethod
    def clear_findings(cls) -> None:
        """Clear all findings."""
        cls._findings.clear()

    @classmethod
    def get_findings(cls, hunt_id: uuid.UUID) -> List[HuntFindingResponse]:
        """Get all findings for a hunt."""
        return cls._findings.get(hunt_id, [])

    @classmethod
    def create_finding(
        cls, hunt_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID, details: str
    ) -> HuntFindingResponse:
        """Create and add a finding to a hunt."""
        cleaned_type = str(entity_type).strip()

        # Check if already exists to prevent duplicate findings
        existing = cls.get_findings(hunt_id)
        for f in existing:
            if f.entity_type == cleaned_type and f.entity_id == entity_id:
                return f

        finding_id = uuid.uuid4()
        finding = HuntFindingResponse(
            finding_id=finding_id,
            hunt_id=hunt_id,
            entity_type=cleaned_type,
            entity_id=entity_id,
            details=details,
            created_at=datetime.now(timezone.utc),
        )
        cls._findings.setdefault(hunt_id, []).append(finding)
        return finding
