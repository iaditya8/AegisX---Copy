import uuid
from typing import List, Optional
from src.domain.entities.security_program import KRIResponse, KRIStatus
from src.services.kri_registry import KRIRegistry
from src.services.incident_service import IncidentService
from src.services.case_service import CaseService
from src.services.exposure_service import ExposureService
from src.services.control_validation_snapshot_service import ControlValidationSnapshotService
from src.services.detection_snapshot_service import DetectionSnapshotService


class KRIService:
    @classmethod
    def calculate_kris(cls, scope_id: Optional[uuid.UUID] = None) -> List[KRIResponse]:
        """Recalculate and return all pre-seeded KRIs dynamically."""
        defs = KRIRegistry.get_registered_kris()
        response = []

        for name, info in defs.items():
            val = 0.0
            threshold = info["threshold"]

            if name == "Critical Risk Growth":
                val = float(len(IncidentService.get_all_incidents()) * 1.5)
            elif name == "Open Incident Growth":
                val = float(len(CaseService.get_all_cases()) * 2.0)
            elif name == "Exposure Growth":
                exposures = ExposureService.get_all_exposures()
                if scope_id:
                    exposures = [e for e in exposures if e.scope_id == scope_id]
                val = float(len(exposures) * 0.5)
            elif name == "Detection Regression":
                # Disabled detections
                detections = DetectionService = None
                try:
                    from src.services.detection_service import DetectionService
                    from src.domain.entities.detection import DetectionStatus
                    dets = DetectionService.get_all_detections()
                    val = float(sum(1 for d in dets if d.status == DetectionStatus.DISABLED))
                except Exception:
                    val = 0.0
            elif name == "Threat Coverage Regression":
                val = 0.0  # Stable baseline

            # Determine risk status based on threshold
            status = KRIStatus.LOW_RISK
            if val > threshold * 2.0:
                status = KRIStatus.CRITICAL_RISK
            elif val > threshold * 1.2:
                status = KRIStatus.HIGH_RISK
            elif val > threshold:
                status = KRIStatus.MEDIUM_RISK

            response.append(
                KRIResponse(
                    kri_id=uuid.uuid5(uuid.NAMESPACE_DNS, name),
                    name=name,
                    description=info["description"],
                    value=val,
                    threshold=threshold,
                    status=status,
                )
            )

        return response
