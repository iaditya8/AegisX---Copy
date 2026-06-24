import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MonitoringEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    change_type: str
    asset_id: uuid.UUID
    finding_id: Optional[uuid.UUID] = None
    previous_state: Optional[str] = None
    current_state: Optional[str] = None
    timestamp: datetime
    fingerprint: str


class MonitoringEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    change_type: str
    asset_id: uuid.UUID
    finding_id: Optional[uuid.UUID] = None
    previous_state: Optional[str] = None
    current_state: Optional[str] = None
    timestamp: datetime
    fingerprint: str


class MonitoringSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    added_assets: int
    removed_assets: int
    modified_assets: int
    added_findings: int
    resolved_findings: int
    rediscovered_findings: int
    risk_increases: int
    risk_decreases: int
    governance_changes: int
