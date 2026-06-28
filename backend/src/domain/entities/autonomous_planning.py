import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class PlanPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PlanStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class MilestoneType(str, Enum):
    REMEDIATION = "REMEDIATION"
    VALIDATION = "VALIDATION"
    DEPLOYMENT = "DEPLOYMENT"
    AUDIT = "AUDIT"


class MilestoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    milestone_id: uuid.UUID
    name: str
    milestone_type: MilestoneType
    target_entity_id: uuid.UUID
    status: str  # PENDING, IN_PROGRESS, COMPLETED
    due_date: datetime
    completed_at: Optional[datetime] = None


class RoadmapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    roadmap_id: uuid.UUID
    optimized_milestone_ids: List[uuid.UUID]
    estimated_effort_days: float
    resource_utilization_coefficient: float


class PlanningRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: uuid.UUID
    plan_fingerprint: str
    category: str
    name: str
    status: PlanStatus
    priority: PlanPriority
    scope_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    milestones: List[MilestoneResponse] = []
    roadmap: Optional[RoadmapResponse] = None


class PlanningSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_plans: int
    approved_count: int
    active_count: int
    closed_count: int
    average_progress: float  # average ratio of completed milestones


class PlanningHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    plan_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
