import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AnalyticsSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnalyticsStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVIEW = "REVIEW"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class KPIStatus(str, Enum):
    ON_TARGET = "ON_TARGET"
    AT_RISK = "AT_RISK"
    OFF_TARGET = "OFF_TARGET"


class KRIStatus(str, Enum):
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"
    CRITICAL_RISK = "CRITICAL_RISK"


class AnalyticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    analytics_id: uuid.UUID
    analytics_fingerprint: str
    analytics_name: str
    description: str
    status: AnalyticsStatus
    scope_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class AnalystPerformanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    analyst_id: uuid.UUID
    analyst_name: str
    alerts_handled: int
    incidents_handled: int
    cases_handled: int
    average_response_time: float
    average_resolution_time: float
    analyst_score: float


class OperationalKPIResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kpi_id: uuid.UUID
    kpi_name: str
    current_value: float
    target_value: float
    status: KPIStatus
    calculated_at: datetime


class OperationalKRIResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kri_id: uuid.UUID
    kri_name: str
    current_value: float
    threshold_value: float
    status: KRIStatus
    calculated_at: datetime


class AnalyticsHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    analytics_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
