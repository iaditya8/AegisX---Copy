import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class FindingResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    asset_port_id: Optional[uuid.UUID] = None
    asset_service_id: Optional[uuid.UUID] = None
    title: str
    description: Optional[str] = None
    severity: str
    status: str
    template_id: str
    template_name: str
    source_plugin: str
    first_seen: datetime
    last_seen: datetime
    created_at: datetime
    updated_at: datetime
    fingerprint: str
    metadata_json: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class FindingEvidenceResponse(BaseModel):
    id: uuid.UUID
    finding_id: uuid.UUID
    evidence_type: str
    raw_request: Optional[str] = None
    raw_response: Optional[str] = None
    matched_at: Optional[str] = None
    matcher_name: Optional[str] = None
    matcher_value: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    evidence_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FindingHistoryResponse(BaseModel):
    id: uuid.UUID
    finding_id: uuid.UUID
    change_type: str
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    changed_by: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
