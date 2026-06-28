import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from src.domain.entities.cyber_resilience import RecoveryObjectiveType, RecoveryObjectiveResponse


class RecoveryObjectiveRecord:
    def __init__(
        self,
        objective_id: uuid.UUID,
        resilience_id: uuid.UUID,
        objective_type: RecoveryObjectiveType,
        target_value: float,
        current_value: float,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.objective_id = objective_id
        self.resilience_id = resilience_id
        self.objective_type = objective_type
        self.target_value = target_value
        self.current_value = current_value
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)


class RecoveryObjectiveService:
    # in-memory store: (resilience_id, objective_type) -> RecoveryObjectiveRecord
    _objectives: Dict[Tuple[uuid.UUID, RecoveryObjectiveType], RecoveryObjectiveRecord] = {}

    @classmethod
    def clear_objectives(cls) -> None:
        """Clear all recovery objectives."""
        cls._objectives.clear()

    @classmethod
    def set_objective(
        cls,
        resilience_id: uuid.UUID,
        objective_type: RecoveryObjectiveType,
        target_value: float,
        current_value: float,
    ) -> RecoveryObjectiveRecord:
        """Create or update a recovery objective (RTO/RPO) for a resilience record."""
        key = (resilience_id, objective_type)
        existing = cls._objectives.get(key)
        if existing:
            existing.target_value = target_value
            existing.current_value = current_value
            existing.updated_at = datetime.now(timezone.utc)
            return existing

        record = RecoveryObjectiveRecord(
            objective_id=uuid.uuid4(),
            resilience_id=resilience_id,
            objective_type=objective_type,
            target_value=target_value,
            current_value=current_value,
        )
        cls._objectives[key] = record
        return record

    @classmethod
    def get_objectives(cls, resilience_id: uuid.UUID) -> List[RecoveryObjectiveResponse]:
        """Get all recovery objectives associated with a resilience record."""
        recs = [r for r in cls._objectives.values() if r.resilience_id == resilience_id]
        return [cls.to_response(r) for r in recs]

    @classmethod
    def calculate_compliance(cls, target: float, current: float) -> float:
        """Calculate compliance percentage: min(target, current) / target * 100."""
        if target <= 0.0:
            return 100.0 if current <= 0.0 else 0.0
        return round(float(min(target, current) / target * 100.0), 2)

    @classmethod
    def get_resilience_objective_compliance(cls, resilience_id: uuid.UUID) -> float:
        """Get average compliance percentage across RTO/RPO objectives."""
        recs = [r for r in cls._objectives.values() if r.resilience_id == resilience_id]
        if not recs:
            return 100.0
        comp_sum = sum(cls.calculate_compliance(r.target_value, r.current_value) for r in recs)
        return round(comp_sum / len(recs), 2)

    @classmethod
    def to_response(cls, record: RecoveryObjectiveRecord) -> RecoveryObjectiveResponse:
        """Convert record to response schema."""
        comp = cls.calculate_compliance(record.target_value, record.current_value)
        return RecoveryObjectiveResponse(
            objective_id=record.objective_id,
            objective_type=record.objective_type,
            target_value=record.target_value,
            current_value=record.current_value,
            compliance_percentage=comp,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
