import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ControlSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ControlStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    RETIRED = "RETIRED"


class ValidationStatus(str, Enum):
    PASSED = "PASSED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ControlType(str, Enum):
    DETECTION = "DETECTION"
    PREVENTIVE = "PREVENTIVE"
    CORRECTIVE = "CORRECTIVE"
    COMPENSATING = "COMPENSATING"
    MONITORING = "MONITORING"


class ControlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    control_id: uuid.UUID
    control_fingerprint: str
    name: str
    description: str
    control_type: ControlType
    severity: ControlSeverity
    status: ControlStatus
    effectiveness_score: float
    attack_techniques: List[str]
    scope_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class ValidationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    validation_id: uuid.UUID
    control_id: uuid.UUID
    validation_status: ValidationStatus
    effectiveness_score: float
    attack_technique: str
    evidence: str
    created_at: datetime


class ControlHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    control_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
