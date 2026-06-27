import uuid
from typing import List, Optional
from src.domain.entities.security_program import KPIResponse, KPIStatus
from src.services.kpi_registry import KPIRegistry
from src.services.incident_service import IncidentService
from src.services.case_service import CaseService
from src.services.exposure_service import ExposureService
from src.services.control_validation_snapshot_service import ControlValidationSnapshotService
from src.services.detection_snapshot_service import DetectionSnapshotService
from src.services.hunt_snapshot_service import HuntSnapshotService


class KPIService:
    @classmethod
    def calculate_kpis(cls, scope_id: Optional[uuid.UUID] = None) -> List[KPIResponse]:
        """Recalculate and return all pre-seeded KPIs dynamically."""
        defs = KPIRegistry.get_registered_kpis()
        response = []

        for name, info in defs.items():
            val = 0.0
            target = info["target"]

            if name == "Mean Time To Detect":
                # MTTR/MTTD based on local incident counts
                val = float(min(15.0 + len(IncidentService.get_all_incidents()) * 2.5, 100.0))
            elif name == "Mean Time To Respond":
                val = float(min(30.0 + len(CaseService.get_all_cases()) * 4.0, 120.0))
            elif name == "Critical Exposure Count":
                exposures = ExposureService.get_all_exposures()
                if scope_id:
                    exposures = [e for e in exposures if e.scope_id == scope_id]
                val = float(sum(1 for e in exposures if e.status.value in ["OPEN", "VALIDATED"] and e.severity.value in ["HIGH", "CRITICAL"]))
            elif name == "Control Effectiveness Score":
                snap = ControlValidationSnapshotService.get_snapshot(scope_id)
                val = float(snap["summary"]["average_effectiveness"])
            elif name == "Detection Coverage Score":
                # Query detection snapshot score
                snap = DetectionSnapshotService.get_snapshot()
                val = float(snap.get("coverage_score", 100.0) if isinstance(snap, dict) else 100.0)
            elif name == "Threat Hunt Coverage":
                snap = HuntSnapshotService.get_snapshot(scope_id)
                val = float(snap.get("coverage", {}).get("hunt_coverage", 100.0))

            # Determine KPI status based on target
            status = KPIStatus.ON_TARGET
            if name in ["Mean Time To Detect", "Mean Time To Respond", "Critical Exposure Count"]:
                # Lower is better
                if val > target * 1.5:
                    status = KPIStatus.OFF_TARGET
                elif val > target:
                    status = KPIStatus.AT_RISK
            else:
                # Higher is better
                if val < target * 0.7:
                    status = KPIStatus.OFF_TARGET
                elif val < target:
                    status = KPIStatus.AT_RISK

            response.append(
                KPIResponse(
                    kpi_id=uuid.uuid5(uuid.NAMESPACE_DNS, name),
                    name=name,
                    description=info["description"],
                    value=val,
                    target=target,
                    status=status,
                )
            )

        return response
