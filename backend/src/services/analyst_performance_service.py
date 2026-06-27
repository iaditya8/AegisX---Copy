import uuid
from typing import Dict, List, Any
from src.domain.entities.security_operations_analytics import AnalystPerformanceResponse


class AnalystRecord:
    def __init__(
        self,
        analyst_id: uuid.UUID,
        analyst_name: str,
        alerts_handled: int,
        incidents_handled: int,
        cases_handled: int,
        average_response_time: float,
        average_resolution_time: float,
    ):
        self.analyst_id = analyst_id
        self.analyst_name = analyst_name
        self.alerts_handled = alerts_handled
        self.incidents_handled = incidents_handled
        self.cases_handled = cases_handled
        self.average_response_time = average_response_time
        self.average_resolution_time = average_resolution_time
        self.analyst_score = 0.0


class AnalystPerformanceService:
    # in-memory store: analyst_id -> AnalystRecord
    _analysts: Dict[uuid.UUID, AnalystRecord] = {}

    @classmethod
    def clear_analysts(cls) -> None:
        """Clear the analyst store."""
        cls._analysts.clear()

    @classmethod
    def seed_analysts_if_empty(cls) -> None:
        """Pre-seed standard analysts to simulate performance rankings."""
        if cls._analysts:
            return

        analyst1_id = uuid.UUID("1a1a1a1a-1a1a-1a1a-1a1a-1a1a1a1a1a1a")
        analyst2_id = uuid.UUID("2b2b2b2b-2b2b-2b2b-2b2b-2b2b2b2b2b2b")

        cls._analysts[analyst1_id] = AnalystRecord(
            analyst_id=analyst1_id,
            analyst_name="Alice Vance",
            alerts_handled=150,
            incidents_handled=12,
            cases_handled=5,
            average_response_time=5.2,
            average_resolution_time=22.4,
        )

        cls._analysts[analyst2_id] = AnalystRecord(
            analyst_id=analyst2_id,
            analyst_name="Bob Smith",
            alerts_handled=90,
            incidents_handled=8,
            cases_handled=4,
            average_response_time=12.5,
            average_resolution_time=45.2,
        )
        cls.calculate()

    @classmethod
    def calculate(cls) -> None:
        """Calculate and update analyst scores based on handles and response times."""
        for rec in cls._analysts.values():
            # Higher alert counts + faster response/resolution = higher score
            vol_score = rec.alerts_handled * 0.4 + rec.incidents_handled * 2.0 + rec.cases_handled * 5.0
            time_penalty = rec.average_response_time * 0.8 + rec.average_resolution_time * 0.4
            raw_score = max(0.0, 100.0 - time_penalty + vol_score * 0.3)
            rec.analyst_score = round(min(100.0, raw_score), 2)

    @classmethod
    def get_analysts(cls) -> List[AnalystPerformanceResponse]:
        """List all analysts."""
        cls.seed_analysts_if_empty()
        return [cls.to_response(a) for a in cls._analysts.values()]

    @classmethod
    def get_rankings(cls) -> List[AnalystPerformanceResponse]:
        """Rank analysts by performance score descending."""
        cls.seed_analysts_if_empty()
        sorted_analysts = sorted(cls._analysts.values(), key=lambda x: x.analyst_score, reverse=True)
        return [cls.to_response(a) for a in sorted_analysts]

    @classmethod
    def to_response(cls, record: AnalystRecord) -> AnalystPerformanceResponse:
        return AnalystPerformanceResponse(
            analyst_id=record.analyst_id,
            analyst_name=record.analyst_name,
            alerts_handled=record.alerts_handled,
            incidents_handled=record.incidents_handled,
            cases_handled=record.cases_handled,
            average_response_time=record.average_response_time,
            average_resolution_time=record.average_resolution_time,
            analyst_score=record.analyst_score,
        )
