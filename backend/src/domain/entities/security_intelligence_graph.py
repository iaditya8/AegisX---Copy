import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class NodeType(str, Enum):
    ASSET = "ASSET"
    RISK = "RISK"
    COMPLIANCE = "COMPLIANCE"
    POSTURE = "POSTURE"
    RESILIENCE = "RESILIENCE"
    KNOWLEDGE = "KNOWLEDGE"
    THREAT_INTEL = "THREAT_INTEL"
    INCIDENT = "INCIDENT"
    CASE = "CASE"
    INVESTIGATION = "INVESTIGATION"


class EdgeType(str, Enum):
    AFFECTS = "AFFECTS"
    CONTAINED_IN = "CONTAINED_IN"
    MITIGATES = "MITIGATES"
    MAPS_TO = "MAPS_TO"
    CORRELATES_WITH = "CORRELATES_WITH"
    TRIGGERS = "TRIGGERS"


class GraphComponentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    STABLE = "STABLE"
    DEPRECATED = "DEPRECATED"


class GraphNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    node_id: uuid.UUID
    node_fingerprint: str
    node_type: NodeType
    entity_id: uuid.UUID
    status: GraphComponentStatus
    scope_id: Optional[uuid.UUID] = None


class GraphEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    edge_id: uuid.UUID
    edge_fingerprint: str
    source_id: uuid.UUID
    target_id: uuid.UUID
    edge_type: EdgeType
    weight: float
    status: GraphComponentStatus
    scope_id: Optional[uuid.UUID] = None


class GraphPathResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    path_id: uuid.UUID
    nodes: List[GraphNodeResponse]
    edges: List[GraphEdgeResponse]
    metrics: dict


class GraphAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    centrality: dict
    impact_paths: List[GraphPathResponse]


class GraphSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_nodes: int
    total_edges: int
    density: float
    average_weight: float


class GraphHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    component_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
