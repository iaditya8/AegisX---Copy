import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class FabricPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FabricStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"


class PropagationMode(str, Enum):
    DIRECT = "DIRECT"
    WEIGHTED = "WEIGHTED"
    CASCADING = "CASCADING"


class ConfidencePropagationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    propagation_id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    mode: PropagationMode
    confidence_score: float
    decay_factor: float
    timestamp: datetime


class FabricCorrelationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    correlation_id: uuid.UUID
    domain_source: str
    domain_target: str
    relationship_strength: float


class FabricIntelligenceNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    node_id: uuid.UUID
    node_fingerprint: str
    source_type: str
    status: FabricStatus
    priority: FabricPriority
    scope_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    confidence_weights: Dict[str, float] = {}
    target_links: List[uuid.UUID] = []


class FabricSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_nodes: int
    active_count: int
    suspended_count: int
    terminated_count: int
    average_confidence: float


class FabricHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    fabric_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
