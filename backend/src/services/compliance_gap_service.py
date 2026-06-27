import uuid
from typing import List
from src.domain.entities.governance_risk_compliance import ComplianceGapResponse


class ComplianceGapService:
    @classmethod
    def get_gaps(
        cls, assessment_id: uuid.UUID, control_count: int, evidence_count: int
    ) -> List[ComplianceGapResponse]:
        """Compute missing controls, missing evidence, and compliance deficiencies."""
        gaps = []
        if control_count == 0:
            gaps.append(
                ComplianceGapResponse(
                    gap_id=uuid.uuid4(),
                    assessment_id=assessment_id,
                    gap_type="MISSING_CONTROLS",
                    description="No framework controls mapped to this assessment.",
                    remediation_plan="Map standard Controls/Policies to complete coverage.",
                )
            )

        if evidence_count < control_count:
            gaps.append(
                ComplianceGapResponse(
                    gap_id=uuid.uuid4(),
                    assessment_id=assessment_id,
                    gap_type="MISSING_EVIDENCE",
                    description=f"Only {evidence_count} of {control_count} controls have evidence mapped.",
                    remediation_plan="Upload compliance evidence hashes to close gaps.",
                )
            )

        return gaps

    @classmethod
    def calculate(cls) -> None:
        """Run compliance gap tracking logic (read-only derived intelligence)."""
        pass
