import uuid
from typing import Dict, List

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
