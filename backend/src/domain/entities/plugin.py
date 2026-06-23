import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PluginManifest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    version: str
    entry_point: str = Field(..., min_length=1, max_length=255)
    capabilities: List[str] = Field(..., min_length=1)
    permissions: List[str] = Field(default_factory=list)
    timeout: int = Field(..., gt=0)

    @field_validator("version")
    @classmethod
    def validate_semver(cls, v: str) -> str:
        semver_regex = (
            r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
            r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
            r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
            r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
        )
        if not re.match(semver_regex, v):
            raise ValueError(
                "Version must follow Semantic Versioning (e.g. 1.0.0, 1.2.5, 2.0.0)"
            )
        return v


class PluginCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    version: str
    manifest: PluginManifest

    @field_validator("version")
    @classmethod
    def validate_semver(cls, v: str) -> str:
        semver_regex = (
            r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
            r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
            r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
            r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
        )
        if not re.match(semver_regex, v):
            raise ValueError("Version must follow Semantic Versioning")
        return v


class PluginUpdate(BaseModel):
    state: Optional[str] = Field(None, pattern="^(draft|approved|disabled|deprecated)$")


class PluginResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    manifest: Dict[str, Any]
    state: str
    installed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PluginEventResponse(BaseModel):
    id: uuid.UUID
    plugin_id: uuid.UUID
    event_type: str
    correlation_id: Optional[uuid.UUID] = None
    workflow_id: Optional[uuid.UUID] = None
    scan_run_id: Optional[uuid.UUID] = None
    payload: Optional[Dict[str, Any]] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
