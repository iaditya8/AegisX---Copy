import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PostureSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskStatus(str, Enum):
    OPEN = "OPEN"
    ACCEPTED = "ACCEPTED"
    MITIGATED = "MITIGATED"
    CLOSED = "CLOSED"


class RiskCategory(str, Enum):
    ATTACK_SURFACE = "ATTACK_SURFACE"
    VULNERABILITY = "VULNERABILITY"
    DETECTION_GAP = "DETECTION_GAP"
    THREAT_EXPOSURE = "THREAT_EXPOSURE"
    COMPLIANCE = "COMPLIANCE"
    IDENTITY = "IDENTITY"
    CONFIGURATION = "CONFIGURATION"
    OPERATIONAL = "OPERATIONAL"


class SecurityPostureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    posture_id: uuid.UUID
    posture_fingerprint: str
    title: str
    description: str
    posture_score: float
    risk_score: float
    severity: PostureSeverity
    category: RiskCategory
    status: RiskStatus
    owner: Optional[str] = None
    asset_id: uuid.UUID
    risk_source: str
    scope_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class RiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    risk_id: uuid.UUID
    risk_fingerprint: str
    title: str
    description: str
    category: RiskCategory
    severity: PostureSeverity
    likelihood: float
    impact: float
    risk_score: float
    status: RiskStatus
    created_at: datetime
    updated_at: datetime


class PostureHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    posture_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
