from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RecommendationType(str, Enum):
    PATCH = "PATCH"
    INVESTIGATE = "INVESTIGATE"
    HARDEN = "HARDEN"
    REVIEW = "REVIEW"
    MONITOR = "MONITOR"
    VALIDATE = "VALIDATE"


class RecommendationPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SupportingFactor(BaseModel):
    factor: str
    impact: float


class RecommendationResponse(BaseModel):
    recommendation_id: str
    priority: RecommendationPriority
    type: RecommendationType
    asset_id: str
    finding_id: Optional[str] = None
    title: str
    reason: str
    risk_score: float
    supporting_factors: List[SupportingFactor] = Field(default_factory=list)


class PriorityRankingResponse(BaseModel):
    id: str
    name: str
    score: float
    rank: int
    type: str  # asset, finding, technology, product
    details: Dict[str, Any] = Field(default_factory=dict)


class InvestigationGuidanceResponse(BaseModel):
    finding_id: Optional[str] = None
    asset_id: str
    steps: List[str] = Field(default_factory=list)


class RecommendationSnapshotResponse(BaseModel):
    asset_id: str
    total_recommendations: int
    by_priority: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
