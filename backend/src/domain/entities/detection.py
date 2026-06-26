import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class DetectionSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DetectionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    DEPRECATED = "DEPRECATED"


class CoverageStatus(str, Enum):
    COVERED = "COVERED"
    PARTIALLY_COVERED = "PARTIALLY_COVERED"
    NOT_COVERED = "NOT_COVERED"


class DetectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    detection_id: uuid.UUID
    detection_fingerprint: str
    name: str
    description: str
    severity: DetectionSeverity
    status: DetectionStatus
    attack_techniques: List[str]
    created_at: datetime
    updated_at: datetime
    scope_id: Optional[uuid.UUID] = None


class DetectionCoverageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    technique_id: str
    coverage_status: CoverageStatus
    detection_count: int
    coverage_score: float


class DetectionHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    detection_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str

