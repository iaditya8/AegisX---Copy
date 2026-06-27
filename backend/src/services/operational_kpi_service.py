import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from src.domain.entities.security_operations_analytics import (
    KPIStatus,
    OperationalKPIResponse,
)
from src.services.soc_kpi_registry import SOCKPIRegistry


class KPIRecord:
    def __init__(
        self,
        kpi_id: uuid.UUID,
        kpi_name: str,
        current_value: float,
        target_value: float,
        status: KPIStatus,
        calculated_at: Optional[datetime] = None,
    ):
        self.kpi_id = kpi_id
        self.kpi_name = kpi_name
        self.current_value = current_value
        self.target_value = target_value
        self.status = status
        self.calculated_at = calculated_at or datetime.now(timezone.utc)


class OperationalKPIService:
    # in-memory store: kpi_name -> KPIRecord
    _kpis: Dict[str, KPIRecord] = {}

    @classmethod
    def clear_kpis(cls) -> None:
        """Clear the KPI store."""
        cls._kpis.clear()

    @classmethod
    def seed_kpis_if_empty(cls) -> None:
        """Pre-seed standard operational KPIs."""
        if cls._kpis:
            return

        for kpi in SOCKPIRegistry.list_types():
            cls._kpis[kpi] = KPIRecord(
                kpi_id=uuid.uuid4(),
                kpi_name=kpi,
                current_value=15.0 if "Mean Time" in kpi else 85.0,
                target_value=10.0 if "Mean Time" in kpi else 90.0,
                status=KPIStatus.AT_RISK,
            )
        cls.calculate()

    @classmethod
    def calculate(cls) -> None:
        """Calculate and refresh KPI targets compliance status."""
        for rec in cls._kpis.values():
            if "Mean Time" in rec.kpi_name:
                # For times, smaller is better
                if rec.current_value <= rec.target_value:
                    rec.status = KPIStatus.ON_TARGET
                elif rec.current_value <= rec.target_value * 1.5:
                    rec.status = KPIStatus.AT_RISK
                else:
                    rec.status = KPIStatus.OFF_TARGET
            else:
                # For rates, higher is better
                if rec.current_value >= rec.target_value:
                    rec.status = KPIStatus.ON_TARGET
                elif rec.current_value >= rec.target_value * 0.85:
                    rec.status = KPIStatus.AT_RISK
                else:
                    rec.status = KPIStatus.OFF_TARGET

            rec.calculated_at = datetime.now(timezone.utc)

    @classmethod
    def get_kpis(cls) -> List[OperationalKPIResponse]:
        """Get all operational KPIs response schemas."""
        cls.seed_kpis_if_empty()
        return [cls.to_response(k) for k in cls._kpis.values()]

    @classmethod
    def set_kpi(
        cls, kpi_name: str, current_value: float, target_value: float
    ) -> KPIRecord:
        """Manually update or set a KPI."""
        if not SOCKPIRegistry.validate(kpi_name):
            raise ValueError(f"Invalid KPI: {kpi_name}")

        existing = cls._kpis.get(kpi_name)
        if existing:
            existing.current_value = current_value
            existing.target_value = target_value
            cls.calculate()
            return existing

        record = KPIRecord(
            kpi_id=uuid.uuid4(),
            kpi_name=kpi_name,
            current_value=current_value,
            target_value=target_value,
            status=KPIStatus.AT_RISK,
        )
        cls._kpis[kpi_name] = record
        cls.calculate()
        return record

    @classmethod
    def to_response(cls, record: KPIRecord) -> OperationalKPIResponse:
        return OperationalKPIResponse(
            kpi_id=record.kpi_id,
            kpi_name=record.kpi_name,
            current_value=record.current_value,
            target_value=record.target_value,
            status=record.status,
            calculated_at=record.calculated_at,
        )
