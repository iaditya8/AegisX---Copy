import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    TRIAGED = "TRIAGED"
    INVESTIGATING = "INVESTIGATING"
    ESCALATED = "ESCALATED"
    CONTAINED = "CONTAINED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class InvestigationStatus(str, Enum):
    OPEN = "OPEN"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    incident_id: uuid.UUID
    incident_fingerprint: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    owner: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    alert_ids: List[uuid.UUID] = []
    asset_ids: List[uuid.UUID] = []
    finding_ids: List[uuid.UUID] = []
    recommendation_ids: List[uuid.UUID] = []
    remediation_ids: List[uuid.UUID] = []


class InvestigationEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entry_id: uuid.UUID
    incident_id: uuid.UUID
    timestamp: datetime
    analyst: uuid.UUID
    action: str
    notes: str


class IncidentHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    incident_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
