from typing import List, Optional
import uuid
from datetime import datetime, timezone
from sqlalchemy.future import select
from src.domain.entities.cyber_resilience import RecoveryObjectiveType, RecoveryObjectiveResponse
from src.infrastructure.database.models import RecoveryObjective
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.core.tenant import get_current_tenant_id


class RecoveryObjectiveService:
    @classmethod
    async def clear_objectives(cls) -> None:
        """Clear all recovery objectives."""
        pass

    @classmethod
    async def set_objective(
        cls,
        resilience_id: uuid.UUID,
        objective_type: RecoveryObjectiveType,
        target_value: float,
        current_value: float,
        uow: Optional[UnitOfWork] = None,
    ) -> RecoveryObjective:
        """Create or update a recovery objective (RTO/RPO) for a resilience record."""
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        
        async def _set(uow_inst: UnitOfWork) -> RecoveryObjective:
            stmt = select(RecoveryObjective).filter_by(
                resilience_id=resilience_id,
                objective_type=objective_type.value if hasattr(objective_type, 'value') else objective_type
            )
            result = await uow_inst.session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            comp = cls.calculate_compliance(target_value, current_value)
            if existing:
                existing.target_value = target_value
                existing.current_value = current_value
                existing.compliance_percentage = comp
                existing.updated_at = datetime.now(timezone.utc)
                return existing

            record = RecoveryObjective(
                objective_id=uuid.uuid4(),
                resilience_id=resilience_id,
                objective_type=objective_type.value if hasattr(objective_type, 'value') else objective_type,
                target_value=target_value,
                current_value=current_value,
                compliance_percentage=comp,
                tenant_id=tenant_id
            )
            await uow_inst.resilience_repo.save_objective(record)
            return record

        if uow:
            return await _set(uow)
        else:
            async with UnitOfWork() as uow_new:
                record = await _set(uow_new)
                await uow_new.commit()
                return record

    @classmethod
    async def get_objectives(cls, resilience_id: uuid.UUID) -> List[RecoveryObjectiveResponse]:
        """Get all recovery objectives associated with a resilience record."""
        async with UnitOfWork() as uow:
            recs = await uow.resilience_repo.get_objectives(resilience_id)
            return [cls.to_response(r) for r in recs]

    @classmethod
    def calculate_compliance(cls, target: float, current: float) -> float:
        """Calculate compliance percentage: min(target, current) / target * 100."""
        if target <= 0.0:
            return 100.0 if current <= 0.0 else 0.0
        return round(float(min(target, current) / target * 100.0), 2)

    @classmethod
    async def get_resilience_objective_compliance(cls, resilience_id: uuid.UUID, uow: Optional[UnitOfWork] = None) -> float:
        """Get average compliance percentage across RTO/RPO objectives."""
        async def _get(uow_inst: UnitOfWork) -> float:
            recs = await uow_inst.resilience_repo.get_objectives(resilience_id)
            if not recs:
                return 100.0
            comp_sum = sum(cls.calculate_compliance(float(r.target_value), float(r.current_value)) for r in recs)
            return round(comp_sum / len(recs), 2)

        if uow:
            return await _get(uow)
        else:
            async with UnitOfWork() as uow_new:
                return await _get(uow_new)

    @classmethod
    def to_response(cls, record: RecoveryObjective) -> RecoveryObjectiveResponse:
        """Convert record to response schema."""
        comp = cls.calculate_compliance(float(record.target_value), float(record.current_value))
        return RecoveryObjectiveResponse(
            objective_id=record.objective_id,
            objective_type=RecoveryObjectiveType(record.objective_type),
            target_value=float(record.target_value),
            current_value=float(record.current_value),
            compliance_percentage=comp,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
