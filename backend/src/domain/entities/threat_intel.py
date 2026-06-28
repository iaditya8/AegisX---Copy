import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ThreatSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ThreatIntelStatus(str, Enum):
    ACTIVE = "ACTIVE"
    IN_TRIAGE = "IN_TRIAGE"
    FUSED = "FUSED"
    ARCHIVED = "ARCHIVED"


class ThreatIndicatorType(str, Enum):
    IP = "IP"
    DOMAIN = "DOMAIN"
    URL = "URL"
    SHA256 = "SHA256"
    EMAIL = "EMAIL"
    CVE = "CVE"


class ThreatIntelRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    threat_intel_id: uuid.UUID
    threat_intel_fingerprint: str
    value: str
    indicator_type: ThreatIndicatorType
    status: ThreatIntelStatus
    severity: ThreatSeverity
    confidence: Optional[float] = None
    source: str
    tags: List[str]
    scope_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class ThreatIndicatorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    indicator_id: uuid.UUID
    threat_intel_id: uuid.UUID
    value: str
    indicator_type: ThreatIndicatorType


class ThreatIntelActorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    actor_id: uuid.UUID
    name: str
    aliases: List[str]
    target_sectors: List[str]
    origin_country: str


class ThreatFusionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fusion_id: uuid.UUID
    threat_intel_id: uuid.UUID
    fusion_score: float
    actor_confidence: float
    severity: ThreatSeverity


class ThreatIntelSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_threat_records: int
    active_threat_records: int
    archived_threat_records: int
    average_fusion_score: float


class ThreatIntelHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    threat_intel_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
