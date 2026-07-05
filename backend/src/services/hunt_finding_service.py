import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.domain.entities.hunt import HuntFindingResponse
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import HuntFinding
from src.core.tenant import get_current_tenant_id


class HuntFindingService:
    # in-memory store: hunt_id -> list of findings
    _findings: Dict[uuid.UUID, List[HuntFindingResponse]] = {}

    @classmethod
    def clear_findings(cls) -> None:
        """Clear all findings."""
        cls._findings.clear()

    @classmethod
    async def get_findings(cls, hunt_id: uuid.UUID) -> List[HuntFindingResponse]:
        """Get all findings for a hunt."""
        async with UnitOfWork() as uow:
            db_entries = await uow.hunt_repo.list_findings(hunt_id)
            res = [
                HuntFindingResponse(
                    finding_id=e.id,
                    hunt_id=e.hunt_id,
                    entity_type=e.entity_type,
                    entity_id=e.entity_id,
                    details=e.details,
                    created_at=e.created_at,
                )
                for e in db_entries
            ]
            return res

    @classmethod
    async def create_finding(
        cls,
        hunt_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        details: str,
        uow: Optional[UnitOfWork] = None,
    ) -> HuntFindingResponse:
        """Create and add a finding to a hunt."""
        cleaned_type = str(entity_type).strip()

        # Check if already exists in L2 cache to prevent duplicate findings
        existing = await cls.get_findings(hunt_id)
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

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        async def _save(uow_inst: UnitOfWork):
            db_find = HuntFinding(
                tenant_id=tenant_id,
                id=finding_id,
                hunt_id=hunt_id,
                entity_type=cleaned_type,
                entity_id=entity_id,
                details=details,
                created_at=finding.created_at,
            )
            await uow_inst.hunt_repo.save_finding(db_find)

        if uow:
            await _save(uow)
        else:
            async with UnitOfWork() as new_uow:
                await _save(new_uow)
                await new_uow.commit()

        return finding
