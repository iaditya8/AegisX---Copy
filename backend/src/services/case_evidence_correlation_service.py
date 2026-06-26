import uuid
from typing import Any, Dict, List

from src.services.evidence_service import EvidenceService
from src.services.incident_evidence_service import IncidentEvidenceService


class CaseEvidenceCorrelationService:
    @classmethod
    def get_correlated_evidence(
        cls, case_id: uuid.UUID, incident_ids: List[uuid.UUID]
    ) -> Dict[str, Any]:
        """Correlate case-specific evidence with linked incident evidence."""
        # Case evidence collected directly
        case_evidences = [
            ev for ev in EvidenceService.get_all_evidence() if ev.case_id == case_id
        ]

        # Incident evidence references from linked incidents
        incident_evidences = {}
        for inc_id in incident_ids:
            incident_evidences[str(inc_id)] = IncidentEvidenceService.get_evidence(inc_id)

        return {
            "case_evidence": case_evidences,
            "incident_evidence": incident_evidences,
        }
