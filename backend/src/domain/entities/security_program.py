import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ProgramSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ProgramStatus(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"


class KPIStatus(str, Enum):
    ON_TARGET = "ON_TARGET"
    AT_RISK = "AT_RISK"
    OFF_TARGET = "OFF_TARGET"


class KRIStatus(str, Enum):
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"
    CRITICAL_RISK = "CRITICAL_RISK"


class ProgramObjectiveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    objective_id: uuid.UUID
    name: str
    description: str
    completion_percentage: float


class ProgramInitiativeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    initiative_id: uuid.UUID
    name: str
    description: str
    status: str
    completion_percentage: float


class KPIResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kpi_id: uuid.UUID
    name: str
    description: str
    value: float
    target: float
    status: KPIStatus


class KRIResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kri_id: uuid.UUID
    name: str
    description: str
    value: float
    threshold: float
    status: KRIStatus


class SecurityProgramResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    program_id: uuid.UUID
    program_fingerprint: str
    name: str
    description: str
    category: str
    severity: ProgramSeverity
    status: ProgramStatus
    program_score: float
    objectives: List[ProgramObjectiveResponse]
    initiatives: List[ProgramInitiativeResponse]
    kpis: List[KPIResponse]
    kris: List[KRIResponse]
    scope_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class ProgramHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    program_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
