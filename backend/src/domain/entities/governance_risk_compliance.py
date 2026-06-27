import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ComplianceSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ComplianceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    IN_REVIEW = "IN_REVIEW"
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    CLOSED = "CLOSED"


class FrameworkType(str, Enum):
    ISO27001 = "ISO27001"
    NIST_CSF = "NIST_CSF"
    NIST_800_53 = "NIST_800_53"
    CIS_CONTROLS = "CIS_CONTROLS"
    SOC2 = "SOC2"
    PCI_DSS = "PCI_DSS"


class ComplianceAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assessment_id: uuid.UUID
    assessment_fingerprint: str
    framework_type: FrameworkType
    name: str
    description: str
    compliance_score: float
    framework_coverage: float
    control_coverage: float
    evidence_completeness: float
    audit_readiness: float
    status: ComplianceStatus
    scope_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class FrameworkControlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    control_id: uuid.UUID
    control_name: str
    framework_type: FrameworkType
    requirement_id: str
    status: str


class ComplianceEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_id: uuid.UUID
    assessment_id: uuid.UUID
    file_name: str
    file_hash: str
    uploaded_at: datetime


class ComplianceGapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    gap_id: uuid.UUID
    assessment_id: uuid.UUID
    gap_type: str
    description: str
    remediation_plan: str


class ComplianceHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    assessment_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
