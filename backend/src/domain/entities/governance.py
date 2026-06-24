import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class GovernanceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    ACCEPTED_RISK = "ACCEPTED_RISK"
    UNDER_REVIEW = "UNDER_REVIEW"
    EXCEPTION_ACTIVE = "EXCEPTION_ACTIVE"


class ComplianceSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskAcceptanceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRING = "EXPIRING"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class RiskAcceptanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    acceptance_id: uuid.UUID
    asset_id: uuid.UUID
    finding_id: Optional[uuid.UUID] = None
    recommendation_id: Optional[uuid.UUID] = None
    recommendation_fingerprint: str
    approved_by: str
    approved_at: datetime
    expiration_date: datetime
    status: RiskAcceptanceStatus
    reason: str


class ComplianceControlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    control_id: str
    control_name: str
    status: str
    severity: str
    affected_assets: List[uuid.UUID] = []
    affected_findings: List[uuid.UUID] = []


class GovernanceSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    compliant_assets: int
    non_compliant_assets: int
    accepted_risks: int
    expired_acceptances: int
    exception_count: int
    sla_breaches: int
