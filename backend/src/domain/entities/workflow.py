import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class WorkflowBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    definition: Dict[str, Any] = Field(default_factory=dict)


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    definition: Optional[Dict[str, Any]] = None
    state: Optional[str] = Field(None, pattern="^(draft|active|disabled)$")


class WorkflowResponse(WorkflowBase):
    id: uuid.UUID
    owner_id: Optional[uuid.UUID] = None
    state: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScanRunResponse(BaseModel):
    id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    scope_id: Optional[uuid.UUID] = None
    plugin_id: Optional[uuid.UUID] = None
    type: str
    status: str
    start_ts: Optional[datetime] = None
    end_ts: Optional[datetime] = None
    metrics: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowEventResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    event_type: str
    correlation_id: Optional[uuid.UUID] = None
    payload: Optional[Dict[str, Any]] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowStartRequest(BaseModel):
    scope_id: uuid.UUID
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)


class WorkflowStartResponse(BaseModel):
    workflow_id: uuid.UUID
    run_id: uuid.UUID
    status: str
