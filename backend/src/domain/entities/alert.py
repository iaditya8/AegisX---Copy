import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AlertSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"


class AlertType(str, Enum):
    ASSET_DRIFT = "ASSET_DRIFT"
    FINDING_DRIFT = "FINDING_DRIFT"
    RISK_DRIFT = "RISK_DRIFT"
    COMPLIANCE_DRIFT = "COMPLIANCE_DRIFT"
    RISK_ACCEPTANCE_EXPIRATION = "RISK_ACCEPTANCE_EXPIRATION"
    SLA_BREACH = "SLA_BREACH"
    CRITICAL_FINDING = "CRITICAL_FINDING"


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_id: uuid.UUID
    alert_fingerprint: str
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    asset_id: Optional[uuid.UUID] = None
    finding_id: Optional[uuid.UUID] = None
    recommendation_id: Optional[uuid.UUID] = None
    remediation_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    owner: Optional[uuid.UUID] = None
    title: str
    description: str
