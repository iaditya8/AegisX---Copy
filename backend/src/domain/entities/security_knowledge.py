import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class KnowledgeSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class KnowledgeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"


class KnowledgeType(str, Enum):
    PLAYBOOK = "PLAYBOOK"
    RUNBOOK = "RUNBOOK"
    DETECTION_KNOWLEDGE = "DETECTION_KNOWLEDGE"
    THREAT_INTELLIGENCE = "THREAT_INTELLIGENCE"
    INVESTIGATION_GUIDE = "INVESTIGATION_GUIDE"
    INCIDENT_RESPONSE = "INCIDENT_RESPONSE"
    FORENSICS = "FORENSICS"
    COMPLIANCE_REFERENCE = "COMPLIANCE_REFERENCE"


class KnowledgeRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    knowledge_id: uuid.UUID
    knowledge_fingerprint: str
    knowledge_type: KnowledgeType
    title: str
    content: str
    relevance_score: float
    confidence_score: float
    status: KnowledgeStatus
    tags: List[str]
    scope_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class KnowledgeRelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    relationship_id: uuid.UUID
    source_id: uuid.UUID
    source_type: str
    target_id: uuid.UUID
    target_type: str
    relationship_type: str
    weight: float


class KnowledgeRecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recommendation_id: uuid.UUID
    knowledge_id: uuid.UUID
    title: str
    description: str
    rank: int


class KnowledgeSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_knowledge_records: int
    active_knowledge_records: int
    archived_knowledge_records: int
    average_relevance_score: float
    average_confidence_score: float


class KnowledgeHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    knowledge_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
