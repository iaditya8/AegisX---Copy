import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.domain.entities.hunt import HuntHypothesisResponse
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.database.models import HuntHypothesis
from src.core.tenant import get_current_tenant_id


class HuntHypothesisService:
    # in-memory store: hunt_id -> list of hypotheses
    _hypotheses: Dict[uuid.UUID, List[HuntHypothesisResponse]] = {}

    @classmethod
    def clear_hypotheses(cls) -> None:
        """Clear all hypotheses."""
        cls._hypotheses.clear()

    @classmethod
    async def get_hypotheses(cls, hunt_id: uuid.UUID) -> List[HuntHypothesisResponse]:
        """Get all hypotheses for a hunt."""
        async with UnitOfWork() as uow:
            db_entries = await uow.hunt_repo.list_hypotheses(hunt_id)
            res = [
                HuntHypothesisResponse(
                    hypothesis_id=e.id,
                    hunt_id=e.hunt_id,
                    description=e.description,
                    created_at=e.created_at,
                )
                for e in db_entries
            ]
            return res

    @classmethod
    async def create_hypothesis(
        cls,
        hunt_id: uuid.UUID,
        description: str,
        uow: Optional[UnitOfWork] = None,
    ) -> HuntHypothesisResponse:
        """Create and add a hypothesis to a hunt."""
        hypothesis_id = uuid.uuid4()
        hyp = HuntHypothesisResponse(
            hypothesis_id=hypothesis_id,
            hunt_id=hunt_id,
            description=description,
            created_at=datetime.now(timezone.utc),
        )
        cls._hypotheses.setdefault(hunt_id, []).append(hyp)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        async def _save(uow_inst: UnitOfWork):
            db_hyp = HuntHypothesis(
                tenant_id=tenant_id,
                id=hypothesis_id,
                hunt_id=hunt_id,
                description=description,
                created_at=hyp.created_at,
            )
            await uow_inst.hunt_repo.save_hypothesis(db_hyp)

        if uow:
            await _save(uow)
        else:
            async with UnitOfWork() as new_uow:
                await _save(new_uow)
                await new_uow.commit()

        return hyp
