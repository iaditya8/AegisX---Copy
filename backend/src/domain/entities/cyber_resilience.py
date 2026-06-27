import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ResilienceSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ResilienceStatus(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    VALIDATED = "VALIDATED"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"


class RecoveryObjectiveType(str, Enum):
    RTO = "RTO"
    RPO = "RPO"


class ServiceCriticality(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    MISSION_CRITICAL = "MISSION_CRITICAL"


class CyberResilienceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resilience_id: uuid.UUID
    resilience_fingerprint: str
    title: str
    description: str
    service_name: str
    service_criticality: ServiceCriticality
    resilience_score: float
    readiness_score: float
    recovery_confidence_score: float
    status: ResilienceStatus
    scope_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class RecoveryObjectiveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    objective_id: uuid.UUID
    objective_type: RecoveryObjectiveType
    target_value: float
    current_value: float
    compliance_percentage: float
    created_at: datetime
    updated_at: datetime


class ResilienceHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    resilience_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
