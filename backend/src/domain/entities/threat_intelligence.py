import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class IOCType(str, Enum):
    IP_ADDRESS = "IP_ADDRESS"
    DOMAIN = "DOMAIN"
    URL = "URL"
    EMAIL = "EMAIL"
    MD5 = "MD5"
    SHA1 = "SHA1"
    SHA256 = "SHA256"


class IOCSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IOCStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class ThreatFeedType(str, Enum):
    INTERNAL = "INTERNAL"
    COMMUNITY = "COMMUNITY"
    COMMERCIAL = "COMMERCIAL"


class ThreatActorStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class CampaignStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class IOCResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ioc_id: uuid.UUID
    ioc_fingerprint: str
    value: str
    ioc_type: IOCType
    severity: IOCSeverity
    status: IOCStatus
    reputation: int
    feed_type: ThreatFeedType
    created_at: datetime
    updated_at: datetime
    scope_id: Optional[uuid.UUID] = None
    threat_actors: List[str] = []
    campaigns: List[str] = []


class ThreatActorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    actor_id: uuid.UUID
    name: str
    description: str
    aliases: List[str] = []
    severity: IOCSeverity
    status: ThreatActorStatus
    iocs: List[str] = []


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    campaign_id: uuid.UUID
    name: str
    description: str
    aliases: List[str] = []
    severity: IOCSeverity
    status: CampaignStatus
    iocs: List[str] = []
    threat_actors: List[str] = []


class IOCHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ioc_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
