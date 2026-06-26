import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class CaseSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseStatus(str, Enum):
    OPEN = "OPEN"
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class EvidenceStatus(str, Enum):
    COLLECTED = "COLLECTED"
    VERIFIED = "VERIFIED"
    TRANSFERRED = "TRANSFERRED"
    ARCHIVED = "ARCHIVED"


class ChainOfCustodyAction(str, Enum):
    CREATED = "CREATED"
    COLLECTED = "COLLECTED"
    VERIFIED = "VERIFIED"
    TRANSFERRED = "TRANSFERRED"
    ACCESSED = "ACCESSED"
    ARCHIVED = "ARCHIVED"


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: uuid.UUID
    case_fingerprint: str
    title: str
    description: str
    severity: CaseSeverity
    status: CaseStatus
    owner: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    incident_ids: List[uuid.UUID] = []


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_id: uuid.UUID
    case_id: uuid.UUID
    source_entity: str
    source_id: uuid.UUID
    integrity_hash: str
    status: EvidenceStatus
    collected_by: uuid.UUID
    collected_at: datetime


class ChainOfCustodyEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entry_id: uuid.UUID
    evidence_id: uuid.UUID
    action: ChainOfCustodyAction
    actor: uuid.UUID
    timestamp: datetime
    notes: str
    integrity_verified: bool


class CaseHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
