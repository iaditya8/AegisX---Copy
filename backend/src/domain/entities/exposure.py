import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ExposureSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExposureStatus(str, Enum):
    OPEN = "OPEN"
    VALIDATED = "VALIDATED"
    ACCEPTED = "ACCEPTED"
    MITIGATED = "MITIGATED"
    CLOSED = "CLOSED"


class ExposureType(str, Enum):
    MISCONFIGURATION = "MISCONFIGURATION"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"
    EXPOSED_PORT = "EXPOSED_PORT"
    EXPOSED_CREDENTIAL = "EXPOSED_CREDENTIAL"
    WEAK_CONTROL = "WEAK_CONTROL"
    DETECTION_GAP = "DETECTION_GAP"
    ATTACK_SURFACE = "ATTACK_SURFACE"


class ExposureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exposure_id: uuid.UUID
    exposure_fingerprint: str
    title: str
    description: str
    severity: ExposureSeverity
    status: ExposureStatus
    exposure_type: ExposureType
    asset_id: uuid.UUID
    owner: Optional[str] = None
    risk_score: float
    created_at: datetime
    updated_at: datetime


class ExposureHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    exposure_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str


class ExposureFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    finding_id: uuid.UUID
    exposure_id: uuid.UUID
    severity: ExposureSeverity
    category: str
    description: str
    created_at: datetime
