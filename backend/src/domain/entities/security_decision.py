import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class DecisionImpact(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DecisionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RECOMMENDED = "RECOMMENDED"
    COMMITTED = "COMMITTED"
    ARCHIVED = "ARCHIVED"


class DecisionType(str, Enum):
    REMEDIATION = "REMEDIATION"
    MITIGATION = "MITIGATION"
    TRANSFER = "TRANSFER"
    ACCEPTANCE = "ACCEPTANCE"
    COMPLIANCE_CONTROL = "COMPLIANCE_CONTROL"


class DecisionTradeoffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cost_multiplier: float
    risk_reduction_coefficient: float
    estimated_cost: float
    estimated_risk_reduction: float
    net_benefit: float


class DecisionImpactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_impact: DecisionImpact
    operational_impact_score: float
    confidence_score: float
    affected_assets: List[uuid.UUID]


class DecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_id: uuid.UUID
    decision_fingerprint: str
    decision_type: DecisionType
    target_entity_id: uuid.UUID
    option_name: str
    status: DecisionStatus
    scope_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    tradeoff_matrix: Optional[DecisionTradeoffResponse] = None
    impact_metrics: Optional[DecisionImpactResponse] = None


class DecisionSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_decisions: int
    recommended_count: int
    committed_count: int
    archived_count: int
    average_net_benefit: float


class DecisionHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    decision_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
