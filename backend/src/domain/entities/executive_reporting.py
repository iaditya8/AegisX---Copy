import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ExecutiveSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExecutiveReportStatus(str, Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class ScorecardStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    AT_RISK = "AT_RISK"
    CRITICAL = "CRITICAL"


class ExecutiveReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: uuid.UUID
    report_fingerprint: str
    title: str
    description: str
    report_period: str
    status: ExecutiveReportStatus
    overall_risk_score: float
    program_score: float
    scorecard_status: ScorecardStatus
    scope_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class ExecutiveScorecardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scorecard_id: uuid.UUID
    overall_health: float
    risk_score: float
    program_score: float
    kpi_score: float
    kri_score: float
    coverage_score: float
    trend_score: float
    generated_at: datetime


class ExecutiveHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    report_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
