import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.executive_reporting import (
    ExecutiveReportStatus,
    ExecutiveSeverity,
    ScorecardStatus,
    ExecutiveReportResponse,
)
from src.services.executive_reporting_registry import ExecutiveReportingRegistry
from src.services.scorecard_registry import ScorecardRegistry
from src.services.executive_report_fingerprint_service import ExecutiveReportFingerprintService
from src.services.executive_history_service import ExecutiveHistoryService
from src.services.executive_scorecard_service import ExecutiveScorecardService


class ExecutiveReportRecord:
    def __init__(
        self,
        report_id: uuid.UUID,
        report_fingerprint: str,
        title: str,
        description: str,
        report_period: str,
        status: ExecutiveReportStatus,
        overall_risk_score: float,
        program_score: float,
        scorecard_status: ScorecardStatus,
        scope_id: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.report_id = report_id
        self.report_fingerprint = report_fingerprint
        self.title = title
        self.description = description
        self.report_period = report_period
        self.status = status
        self.overall_risk_score = overall_risk_score
        self.program_score = program_score
        self.scorecard_status = scorecard_status
        self.scope_id = scope_id
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)


class ExecutiveReportingService:
    # in-memory store: report_id -> ExecutiveReportRecord
    _reports: Dict[uuid.UUID, ExecutiveReportRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def clear_reports(cls) -> None:
        """Clear all report caches."""
        cls._reports.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_reports(cls) -> List[ExecutiveReportRecord]:
        """Retrieve all executive reports."""
        return list(cls._reports.values())

    @classmethod
    def get_report(cls, report_id: uuid.UUID) -> Optional[ExecutiveReportRecord]:
        """Retrieve an executive report by ID."""
        return cls._reports.get(report_id)

    @classmethod
    def get_report_by_fingerprint(cls, fingerprint: str) -> Optional[ExecutiveReportRecord]:
        """Retrieve a report by fingerprint."""
        report_id = cls._fingerprint_lookup.get(fingerprint)
        if report_id:
            return cls.get_report(report_id)
        return None

    @classmethod
    async def create_or_sync_report(
        cls,
        title: str,
        description: str,
        report_period: str,
        report_type: str,
        scope_id: Optional[uuid.UUID] = None,
        included_entities: Optional[List[str]] = None,
    ) -> ExecutiveReportRecord:
        """Create or synchronize an executive report based on identity rules."""
        if not ExecutiveReportingRegistry.is_valid_type(report_type):
            raise ValueError(f"Unsupported report type: {report_type}")

        fingerprint = ExecutiveReportFingerprintService.generate_fingerprint(
            report_period, scope_id, included_entities
        )
        existing = cls.get_report_by_fingerprint(fingerprint)

        if existing:
            if existing.status == ExecutiveReportStatus.ARCHIVED:
                # Terminal State Rule: ARCHIVED cannot be reactivated
                return existing

            # Re-calculate health scorecard
            card = ExecutiveScorecardService.calculate_scorecard(existing.scope_id)
            changed = False
            
            if existing.overall_risk_score != card.risk_score:
                existing.overall_risk_score = card.risk_score
                changed = True
                ExecutiveHistoryService.record_event(
                    existing.report_id, "RISK_CHANGED", f"Risk score updated: {card.risk_score}"
                )

            if existing.program_score != card.program_score:
                existing.program_score = card.program_score
                changed = True
                ExecutiveHistoryService.record_event(
                    existing.report_id, "SCORE_CHANGED", f"Program score updated: {card.program_score}"
                )

            new_status = ScorecardRegistry.resolve_status(card.overall_health)
            if existing.scorecard_status != new_status:
                existing.scorecard_status = new_status
                changed = True

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
            return existing

        # Create new report record
        report_id = uuid.uuid4()
        card = ExecutiveScorecardService.calculate_scorecard(scope_id)
        scorecard_status = ScorecardRegistry.resolve_status(card.overall_health)

        record = ExecutiveReportRecord(
            report_id=report_id,
            report_fingerprint=fingerprint,
            title=title,
            description=description,
            report_period=report_period,
            status=ExecutiveReportStatus.DRAFT,
            overall_risk_score=card.risk_score,
            program_score=card.program_score,
            scorecard_status=scorecard_status,
            scope_id=scope_id,
        )

        cls._reports[report_id] = record
        cls._fingerprint_lookup[fingerprint] = report_id

        ExecutiveHistoryService.record_event(
            report_id, "CREATED", f"Executive report draft created: '{title}' ({report_period})"
        )
        return record

    @classmethod
    async def sync_reports(cls, db: AsyncSession) -> List[ExecutiveReportRecord]:
        """Continuous sync loop discovering new board and executive review cycles."""
        synced = []

        # 1. Annual Security Board Report
        prog1 = await cls.create_or_sync_report(
            title="Annual Security Board Report",
            description="FY26 Board Audit Report on organizational posture.",
            report_period="2026-FY",
            report_type="BOARD_REPORT",
        )
        synced.append(prog1)

        # 2. Quarterly Threat Review
        prog2 = await cls.create_or_sync_report(
            title="Quarterly Threat Review",
            description="Q2 FY26 Security Review.",
            report_period="2026-Q2",
            report_type="QUARTERLY_REVIEW",
        )
        synced.append(prog2)

        return synced

    @classmethod
    def transition_report_status(
        cls, report_id: uuid.UUID, new_status: ExecutiveReportStatus
    ) -> ExecutiveReportRecord:
        """Safely transition report status enforcing terminal states."""
        report = cls.get_report(report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found")

        if report.status == ExecutiveReportStatus.ARCHIVED:
            # Terminal State Rule: cannot reactivate or modify
            return report

        old_status = report.status
        report.status = new_status
        report.updated_at = datetime.now(timezone.utc)

        ExecutiveHistoryService.record_event(
            report_id,
            "STATUS_CHANGED",
            f"Status transitioned from {old_status.value} to {new_status.value}",
        )
        return report

    @classmethod
    def to_response(cls, record: ExecutiveReportRecord) -> ExecutiveReportResponse:
        """Convert an ExecutiveReportRecord to an ExecutiveReportResponse Pydantic schema."""
        return ExecutiveReportResponse(
            report_id=record.report_id,
            report_fingerprint=record.report_fingerprint,
            title=record.title,
            description=record.description,
            report_period=record.report_period,
            status=record.status,
            overall_risk_score=record.overall_risk_score,
            program_score=record.program_score,
            scorecard_status=record.scorecard_status,
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
