import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from src.domain.entities.security_operations_analytics import (
    KRIStatus,
    OperationalKRIResponse,
)
from src.services.soc_kri_registry import SOCKRIRegistry


class KRIRecord:
    def __init__(
        self,
        kri_id: uuid.UUID,
        kri_name: str,
        current_value: float,
        threshold_value: float,
        status: KRIStatus,
        calculated_at: Optional[datetime] = None,
    ):
        self.kri_id = kri_id
        self.kri_name = kri_name
        self.current_value = current_value
        self.threshold_value = threshold_value
        self.status = status
        self.calculated_at = calculated_at or datetime.now(timezone.utc)


class OperationalKRIService:
    # in-memory store: kri_name -> KRIRecord
    _kris: Dict[str, KRIRecord] = {}

    @classmethod
    def clear_kris(cls) -> None:
        """Clear the KRI store."""
        cls._kris.clear()

    @classmethod
    def seed_kris_if_empty(cls) -> None:
        """Pre-seed standard operational KRIs."""
        if cls._kris:
            return

        for kri in SOCKRIRegistry.list_types():
            cls._kpis = cls._kris[kri] = KRIRecord(
                kri_id=uuid.uuid4(),
                kri_name=kri,
                current_value=4.5,
                threshold_value=5.0,
                status=KRIStatus.LOW_RISK,
            )
        cls.calculate()

    @classmethod
    def calculate(cls) -> None:
        """Calculate and refresh KRI risk thresholds status."""
        for rec in cls._kris.values():
            ratio = rec.current_value / rec.threshold_value if rec.threshold_value > 0 else 1.0
            if ratio >= 1.5:
                rec.status = KRIStatus.CRITICAL_RISK
            elif ratio >= 1.0:
                rec.status = KRIStatus.HIGH_RISK
            elif ratio >= 0.7:
                rec.status = KRIStatus.MEDIUM_RISK
            else:
                rec.status = KRIStatus.LOW_RISK

            rec.calculated_at = datetime.now(timezone.utc)

    @classmethod
    def get_kris(cls) -> List[OperationalKRIResponse]:
        """Get all operational KRIs response schemas."""
        cls.seed_kris_if_empty()
        return [cls.to_response(k) for k in cls._kris.values()]

    @classmethod
    def set_kri(
        cls, kri_name: str, current_value: float, threshold_value: float
    ) -> KRIRecord:
        """Manually update or set a KRI."""
        if not SOCKRIRegistry.validate(kri_name):
            raise ValueError(f"Invalid KRI: {kri_name}")

        existing = cls._kris.get(kri_name)
        if existing:
            existing.current_value = current_value
            existing.threshold_value = threshold_value
            cls.calculate()
            return existing

        record = KRIRecord(
            kri_id=uuid.uuid4(),
            kri_name=kri_name,
            current_value=current_value,
            threshold_value=threshold_value,
            status=KRIStatus.LOW_RISK,
        )
        cls._kris[kri_name] = record
        cls.calculate()
        return record

    @classmethod
    def to_response(cls, record: KRIRecord) -> OperationalKRIResponse:
        return OperationalKRIResponse(
            kri_id=record.kri_id,
            kri_name=record.kri_name,
            current_value=record.current_value,
            threshold_value=record.threshold_value,
            status=record.status,
            calculated_at=record.calculated_at,
        )
# Workaround duplicate variable assignment typo:
OperationalKRIService._kpis = {}
