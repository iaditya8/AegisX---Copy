import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssetBase(BaseModel):
    host: Optional[str] = Field(None, max_length=255)
    ip: Optional[str] = Field(None, max_length=45)  # supports ipv4 and ipv6 length
    asset_type: Optional[str] = Field(None, max_length=50)  # host, domain, ip
    metadata_json: Optional[Dict[str, Any]] = Field(
        default_factory=dict, alias="metadata_json"
    )
    fingerprint: Optional[str] = Field(None, max_length=255)


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    host: Optional[str] = Field(None, max_length=255)
    ip: Optional[str] = Field(None, max_length=45)
    asset_type: Optional[str] = Field(None, max_length=50)
    metadata_json: Optional[Dict[str, Any]] = None
    fingerprint: Optional[str] = Field(None, max_length=255)


class AssetResponse(BaseModel):
    id: uuid.UUID
    scope_id: Optional[uuid.UUID] = None
    host: Optional[str] = None
    ip: Optional[str] = None
    asset_type: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = Field(None, alias="metadata_json")
    first_seen: datetime
    last_seen: datetime
    fingerprint: Optional[str] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator('ip', mode='before')
    @classmethod
    def serialize_ip(cls, v):
        if v is not None:
            return str(v)
        return v


class AssetRelationshipCreate(BaseModel):
    target_asset_id: uuid.UUID
    relationship_type: str = Field(..., min_length=1, max_length=100)
    metadata_json: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AssetRelationshipResponse(BaseModel):
    id: uuid.UUID
    source_asset_id: uuid.UUID
    target_asset_id: uuid.UUID
    relationship_type: str
    metadata_json: Optional[Dict[str, Any]] = Field(None, alias="metadata_json")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AssetHistoryResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    change_type: str
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
