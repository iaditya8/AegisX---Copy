import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RiskSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskQuantificationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ACCEPTED = "ACCEPTED"
    MITIGATED = "MITIGATED"
    CLOSED = "CLOSED"


class RiskScenarioType(str, Enum):
    DATA_BREACH = "DATA_BREACH"
    RANSOMWARE = "RANSOMWARE"
    INSIDER_THREAT = "INSIDER_THREAT"
    SERVICE_OUTAGE = "SERVICE_OUTAGE"
    CLOUD_COMPROMISE = "CLOUD_COMPROMISE"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"


class CyberRiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    risk_id: uuid.UUID
    risk_fingerprint: str
    scenario_type: RiskScenarioType
    title: str
    description: str
    exposure_value: float
    single_loss_expectancy: float
    annualized_loss_expectancy: float
    inherent_risk_score: float
    residual_risk_score: float
    mitigation_effectiveness: float
    status: RiskQuantificationStatus
    scope_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class RiskScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_type: RiskScenarioType
    frequency_label: str
    impact_label: str
    annualized_rate_of_occurrence: float
    exposure_factor: float
    expected_annual_loss: float


class RiskForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    risk_id: uuid.UUID
    quarter: str
    projected_loss: float
    exposure_value: float


class RiskHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    risk_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
