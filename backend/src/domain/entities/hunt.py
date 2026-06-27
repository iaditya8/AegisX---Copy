import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class HuntSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class HuntStatus(str, Enum):
    OPEN = "OPEN"
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    ESCALATED = "ESCALATED"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"


class HuntType(str, Enum):
    IOC_DRIVEN = "IOC_DRIVEN"
    ATTACK_DRIVEN = "ATTACK_DRIVEN"
    DETECTION_GAP = "DETECTION_GAP"
    THREAT_ACTOR_DRIVEN = "THREAT_ACTOR_DRIVEN"
    CAMPAIGN_DRIVEN = "CAMPAIGN_DRIVEN"
    MANUAL = "MANUAL"


class HuntFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    finding_id: uuid.UUID
    hunt_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    details: str
    created_at: datetime


class HuntHypothesisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hypothesis_id: uuid.UUID
    hunt_id: uuid.UUID
    description: str
    created_at: datetime


class HuntHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    hunt_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str


class HuntResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hunt_id: uuid.UUID
    hunt_fingerprint: str
    title: str
    description: str
    hunt_type: HuntType
    severity: HuntSeverity
    status: HuntStatus
    owner_id: Optional[uuid.UUID] = None
    scope_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    hypotheses: List[HuntHypothesisResponse] = []
    findings: List[HuntFindingResponse] = []
    related_entities: List[dict] = []
