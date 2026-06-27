import uuid
from datetime import datetime, timezone
from typing import Optional

from src.domain.entities.executive_reporting import ExecutiveScorecardResponse
from src.services.incident_service import IncidentService
from src.services.security_program_snapshot_service import SecurityProgramSnapshotService
from src.services.control_validation_snapshot_service import ControlValidationSnapshotService


class ExecutiveScorecardService:
    @classmethod
    def calculate_scorecard(
        cls, scope_id: Optional[uuid.UUID] = None
    ) -> ExecutiveScorecardResponse:
        """Compute scorecard health and metrics deterministically."""
        # 1. Risk score based on incident volume
        incidents = IncidentService.get_all_incidents()
        risk_score = float(max(100.0 - len(incidents) * 5.0, 0.0))

        # 2. Program score
        prog_snap = SecurityProgramSnapshotService.get_snapshot(scope_id)
        program_score = float(prog_snap["summary"]["average_program_score"])
        kpi_score = float(prog_snap["summary"]["kpi_performance_rate"])
        kri_score = float(prog_snap["summary"]["kri_exposure_rate"])

        # 3. Coverage score from control snapshot
        ctrl_snap = ControlValidationSnapshotService.get_snapshot(scope_id)
        coverage_score = float(ctrl_snap["summary"]["average_effectiveness"])

        # 4. Trend score
        trend_score = 90.0

        # Composite overall health
        overall_health = round(
            (risk_score * 0.2 + program_score * 0.2 + kpi_score * 0.2 + kri_score * 0.2 + coverage_score * 0.2),
            2,
        )

        return ExecutiveScorecardResponse(
            scorecard_id=uuid.uuid5(uuid.NAMESPACE_DNS, f"scorecard-{str(scope_id or 'global')}"),
            overall_health=overall_health,
            risk_score=risk_score,
            program_score=program_score,
            kpi_score=kpi_score,
            kri_score=kri_score,
            coverage_score=coverage_score,
            trend_score=trend_score,
            generated_at=datetime.now(timezone.utc),
        )
