import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CorrelationResponse(BaseModel):
    """Unified correlation details of an asset."""

    asset_id: uuid.UUID
    ports: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)
    finding_counts: Dict[str, int] = Field(default_factory=dict)
    exposure: str
    risk_factors: List[str] = Field(default_factory=list)


class RiskExplanationResponse(BaseModel):
    """Detailed explanation of a single risk factor contribution."""

    factor: str
    impact: int


class RiskResponse(BaseModel):
    """Unified risk parameters, scores, and explanations for an asset."""

    asset_id: uuid.UUID
    criticality: str
    risk_score: int
    risk_level: str
    exposure: str
    finding_counts: Dict[str, int] = Field(default_factory=dict)
    risk_factors: List[str] = Field(default_factory=list)
    explanations: List[RiskExplanationResponse] = Field(default_factory=list)


class CorrelationRuleCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    condition_expression: dict = Field(...)
    priority_level: str = Field(..., description="critical, high, medium, low")


class CorrelationRuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    status: str
    condition_expression: dict
    priority_level: str
    rule_version: int

    class Config:
        from_attributes = True


class CorrelationClusterSignalResponse(BaseModel):
    id: uuid.UUID
    cluster_id: uuid.UUID
    signal_type: str
    signal_id: uuid.UUID
    added_at: datetime

    class Config:
        from_attributes = True


class CorrelationHistoryResponse(BaseModel):
    id: uuid.UUID
    cluster_id: uuid.UUID
    event_type: str
    details_json: Optional[dict]
    timestamp: datetime

    class Config:
        from_attributes = True


class CorrelationClusterResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    unified_score: float
    score_breakdown_json: Optional[dict]
    status: str
    fingerprint: str
    associated_incident_id: Optional[uuid.UUID]
    signals: List[CorrelationClusterSignalResponse] = Field(default_factory=list)
    history: List[CorrelationHistoryResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ClusterEscalateRequest(BaseModel):
    incident_title: Optional[str] = None
    incident_description: Optional[str] = None
