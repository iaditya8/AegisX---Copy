import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel


class RemediationStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    REMEDIATED = "REMEDIATED"
    ACCEPTED_RISK = "ACCEPTED_RISK"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    DEFERRED = "DEFERRED"


class RemediationHistoryType(str, Enum):
    STATUS_CHANGE = "STATUS_CHANGE"
    OWNER_CHANGE = "OWNER_CHANGE"
    SLA_BREACH = "SLA_BREACH"
    EXCEPTION = "EXCEPTION"
    CREATED = "CREATED"


class OwnerAssignmentModel(BaseModel):
    old_owner: Optional[str] = None
    new_owner: Optional[str] = None
    timestamp: datetime


class RemediationException(BaseModel):
    reason: str
    approved_by: str
    timestamp: datetime


class RemediationHistoryEntry(BaseModel):
    history_id: uuid.UUID
    remediation_id: uuid.UUID
    history_type: RemediationHistoryType
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    actor_id: Optional[uuid.UUID] = None
    timestamp: datetime


class RemediationResponse(BaseModel):
    remediation_id: uuid.UUID
    recommendation_fingerprint: str
    status: RemediationStatus
    owner: Optional[str] = None
    due_date: datetime
    created_at: datetime
    updated_at: datetime
    reason: Optional[str] = None
    approved_by: Optional[str] = None
    exception_approved_at: Optional[datetime] = None
