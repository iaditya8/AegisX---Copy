import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ScopeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., pattern="^(domain|cidr|asset-group)$")
    definition: Dict[str, Any] = Field(default_factory=dict)


class ScopeCreate(ScopeBase):
    pass


class ScopeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[str] = Field(None, pattern="^(domain|cidr|asset-group)$")
    definition: Optional[Dict[str, Any]] = None


class ScopeResponse(ScopeBase):
    id: uuid.UUID
    owner_id: Optional[uuid.UUID] = None
    created_at: datetime
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)
