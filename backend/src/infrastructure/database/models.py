import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
    Float,
    Boolean,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID, ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Index

from src.infrastructure.database.mixins import (
    TenantOwnedMixin,
    AuditMixin,
    VersionedMixin,
    SoftDeleteMixin,
)


class Base(DeclarativeBase):
    pass


from sqlalchemy import event
from src.core.tenant import get_current_tenant_id

@event.listens_for(Base, "before_insert", propagate=True)
def set_tenant_id_before_insert(mapper, connection, target):
    """Automatically populate tenant_id on insert if present on target and not set."""
    if hasattr(target, "tenant_id") and getattr(target, "tenant_id", None) is None:
        tenant_id = get_current_tenant_id()
        if tenant_id:
            target.tenant_id = tenant_id
        else:
            from src.core.tenant import TenantContextError
            raise TenantContextError(
                f"Cannot insert {target.__class__.__name__} without active tenant context."
            )

    # Self-healing for IntelligenceEvent
    if target.__class__.__name__ == "IntelligenceEvent":
        if getattr(target, "domain", None) is None and getattr(target, "event_type", None):
            target.domain = target.event_type.split(".")[0]
        if getattr(target, "entity_id", None) is None and getattr(target, "payload", None):
            payload = target.payload
            if isinstance(payload, dict):
                id_val = None
                for k, v in payload.items():
                    if k.endswith("_id") and v:
                        id_val = v
                        break
                if id_val:
                    import uuid
                    try:
                        target.entity_id = uuid.UUID(id_val) if isinstance(id_val, str) else id_val
                    except ValueError:
                        pass



class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class IntelligenceEvent(Base):
    __tablename__ = "intelligence_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    domain: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String, server_default="pending", nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=text("now()")
    )


class User(Base):
    __tablename__ = "users"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    api_key_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Scope(Base):
    __tablename__ = "scopes"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # domain, cidr, asset-group
    definition: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class Asset(Base):
    __tablename__ = "assets"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="CASCADE"), nullable=True
    )
    host: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(INET, nullable=True)
    asset_type: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # host, domain, ip
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    fingerprint: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class Workflow(Base):
    __tablename__ = "workflows"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    definition: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(String, server_default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Plugin(Base):
    __tablename__ = "plugins"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    manifest: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    state: Mapped[str] = mapped_column(
        String, server_default="draft", nullable=False
    )  # draft, approved, disabled, deprecated
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ScanRun(Base):
    __tablename__ = "scan_runs"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    workflow_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="SET NULL"),
        nullable=True,
    )
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="SET NULL"), nullable=True
    )
    plugin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plugins.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # discovery, port, http, nuclei
    status: Mapped[str] = mapped_column(
        String, server_default="pending", nullable=False
    )
    start_ts: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_ts: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Finding(Base):
    __tablename__ = "findings"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    asset_port_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asset_ports.id", ondelete="SET NULL"),
        nullable=True,
    )
    asset_service_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asset_services.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, server_default="open", nullable=False)
    template_id: Mapped[str] = mapped_column(String, nullable=False)
    template_name: Mapped[str] = mapped_column(String, nullable=False)
    source_plugin: Mapped[str] = mapped_column(String, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {
            "cves": [],
            "cvss": None,
            "epss": None,
            "closed_by_scan": False,
            "last_scan_missing": False,
            "last_detected_scan_run_id": None,
        },
    )


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String, nullable=False)
    raw_request: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    raw_response: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    matched_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    matcher_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    matcher_value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    evidence_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class FindingHistory(Base):
    __tablename__ = "finding_history"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
    )
    change_type: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class Report(Base):
    __tablename__ = "reports"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    workflow_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    format: Mapped[str] = mapped_column(String, nullable=False)  # markdown, html, pdf
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Artifact(Base):
    __tablename__ = "artifacts"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    report_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=True
    )
    scan_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    filename: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mime: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    correlation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class PluginEvent(Base):
    __tablename__ = "plugin_events"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    plugin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    correlation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    workflow_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    scan_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class AssetRelationship(Base):
    __tablename__ = "asset_relationships"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    target_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class AssetHistory(Base):
    __tablename__ = "asset_history"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(
        String, server_default="asset", nullable=False
    )
    change_type: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class CorrelatedFinding(Base):
    __tablename__ = "correlated_findings"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
    )
    correlation_group: Mapped[str] = mapped_column(String, nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class RiskScore(Base):
    __tablename__ = "risk_scores"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class AssetPort(Base):
    __tablename__ = "asset_ports"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    port: Mapped[int] = mapped_column(BigInteger, nullable=False)
    protocol: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("asset_id", "port", "protocol", name="uq_asset_port_protocol"),
    )


class AssetService(Base):
    __tablename__ = "asset_services"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    asset_port_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asset_ports.id", ondelete="CASCADE"),
        nullable=False,
    )
    service_name: Mapped[str] = mapped_column(String, nullable=False)
    product: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    banner: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("asset_port_id", "service_name", name="uq_asset_port_service"),
    )


# ==============================================================================
# CYBER RESILIENCE DOMAIN
# ==============================================================================

class CyberResilienceRecord(Base):
    __tablename__ = "cyber_resilience_records"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    resilience_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    resilience_fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    service_name: Mapped[str] = mapped_column(String, nullable=False)
    service_criticality: Mapped[str] = mapped_column(String, nullable=False)
    resilience_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    readiness_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    recovery_confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class RecoveryObjective(Base):
    __tablename__ = "cyber_resilience_objectives"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    objective_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    resilience_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cyber_resilience_records.resilience_id", ondelete="CASCADE"), nullable=False
    )
    objective_type: Mapped[str] = mapped_column(String, nullable=False)
    target_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    current_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    compliance_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class CyberResilienceHistory(Base):
    __tablename__ = "cyber_resilience_history"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    resilience_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cyber_resilience_records.resilience_id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)


# ==============================================================================
# SOC ANALYTICS DOMAIN
# ==============================================================================

class SOCAnalyticsRecord(Base):
    __tablename__ = "soc_analytics_records"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    analytics_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    analytics_fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    analytics_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class SOCAnalystPerformance(Base):
    __tablename__ = "soc_analyst_performance"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    analyst_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    analyst_name: Mapped[str] = mapped_column(String, nullable=False)
    alerts_handled: Mapped[int] = mapped_column(Integer, nullable=False)
    incidents_handled: Mapped[int] = mapped_column(Integer, nullable=False)
    cases_handled: Mapped[int] = mapped_column(Integer, nullable=False)
    average_response_time: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    average_resolution_time: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    analyst_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)


class SOCOperationalKPI(Base):
    __tablename__ = "soc_operational_kpis"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    kpi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    kpi_name: Mapped[str] = mapped_column(String, nullable=False)
    current_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    target_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class SOCOperationalKRI(Base):
    __tablename__ = "soc_operational_kris"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    kri_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    kri_name: Mapped[str] = mapped_column(String, nullable=False)
    current_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class SOCAnalyticsHistory(Base):
    __tablename__ = "soc_analytics_history"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    analytics_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("soc_analytics_records.analytics_id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)


# ==============================================================================
# GRC INTELLIGENCE DOMAIN
# ==============================================================================

class GRCAssessment(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "grc_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    assessment_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    framework_type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    compliance_score: Mapped[float] = mapped_column(Numeric, nullable=False)
    framework_coverage: Mapped[float] = mapped_column(Numeric, nullable=False)
    control_coverage: Mapped[float] = mapped_column(Numeric, nullable=False)
    evidence_completeness: Mapped[float] = mapped_column(Numeric, nullable=False)
    audit_readiness: Mapped[float] = mapped_column(Numeric, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="SET NULL"), nullable=True
    )

    @property
    def assessment_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        UniqueConstraint("tenant_id", "assessment_fingerprint", name="uq_grc_assessments_tenant_fingerprint"),
        Index("ix_grc_assessments_tenant", "tenant_id"),
        Index("ix_grc_assessments_tenant_status", "tenant_id", "status"),
        Index("ix_grc_assessments_tenant_created", "tenant_id", "created_at"),
    )


class GRCFrameworkControl(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "grc_framework_controls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    control_name: Mapped[str] = mapped_column(String, nullable=False)
    framework_type: Mapped[str] = mapped_column(String, nullable=False)
    requirement_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)

    @property
    def control_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_grc_framework_controls_tenant", "tenant_id"),
    )


class GRCEvidence(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "grc_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc_assessments.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    evidence_uri: Mapped[str] = mapped_column(String, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    @property
    def evidence_id(self) -> uuid.UUID:
        return self.id

    @property
    def uploaded_at(self):
        return self.created_at

    __table_args__ = (
        Index("ix_grc_evidence_tenant", "tenant_id"),
    )


class GRCGap(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "grc_gaps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc_assessments.id", ondelete="CASCADE"), nullable=False
    )
    gap_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    remediation_plan: Mapped[str] = mapped_column(String, nullable=False)

    @property
    def gap_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_grc_gaps_tenant", "tenant_id"),
    )


class GRCHistory(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "grc_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grc_assessments.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_grc_history_tenant", "tenant_id"),
    )


# ==============================================================================
# SECURITY KNOWLEDGE DOMAIN
# ==============================================================================

class SecurityKnowledgeRecord(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "security_knowledge_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    knowledge_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    knowledge_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content_markdown: Mapped[str] = mapped_column(String, nullable=False)
    content_summary: Mapped[str] = mapped_column(String, nullable=False)
    content_embedding_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    relevance_score: Mapped[float] = mapped_column(Numeric, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="SET NULL"), nullable=True
    )

    @property
    def knowledge_id(self) -> uuid.UUID:
        return self.id

    @property
    def content(self) -> str:
        return self.content_markdown

    @content.setter
    def content(self, value: str):
        self.content_markdown = value

    __table_args__ = (
        UniqueConstraint("tenant_id", "knowledge_fingerprint", name="uq_security_knowledge_records_tenant_fingerprint"),
        Index("ix_security_knowledge_records_tenant", "tenant_id"),
        Index("ix_security_knowledge_records_tenant_status", "tenant_id", "status"),
        Index("ix_security_knowledge_records_tenant_created", "tenant_id", "created_at"),
    )


class SecurityKnowledgeRelationship(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "security_knowledge_relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[float] = mapped_column(Numeric, nullable=False)

    @property
    def relationship_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_security_knowledge_relationships_tenant", "tenant_id"),
    )


class SecurityKnowledgeRecommendation(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "security_knowledge_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    knowledge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security_knowledge_records.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    @property
    def recommendation_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_security_knowledge_recommendations_tenant", "tenant_id"),
    )


class SecurityKnowledgeHistory(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "security_knowledge_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    knowledge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security_knowledge_records.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_security_knowledge_history_tenant", "tenant_id"),
    )


# ==============================================================================
# THREAT INTELLIGENCE DOMAIN
# ==============================================================================

class ThreatIntelIOC(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "threat_intel_iocs"

    ioc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    ioc_fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    ioc_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    reputation: Mapped[int] = mapped_column(Integer, nullable=False)
    feed_type: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}", nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="SET NULL"), nullable=True
    )


class ThreatIntelActor(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "threat_intel_actors"

    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)


class ThreatIntelCampaign(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "threat_intel_campaigns"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)


class ThreatIntelIOCActorMapping(Base, TenantOwnedMixin):
    __tablename__ = "threat_intel_ioc_actor_mapping"

    ioc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threat_intel_iocs.ioc_id", ondelete="CASCADE"), primary_key=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threat_intel_actors.actor_id", ondelete="CASCADE"), primary_key=True
    )


class ThreatIntelIOCCampaignMapping(Base, TenantOwnedMixin):
    __tablename__ = "threat_intel_ioc_campaign_mapping"

    ioc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threat_intel_iocs.ioc_id", ondelete="CASCADE"), primary_key=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threat_intel_campaigns.campaign_id", ondelete="CASCADE"), primary_key=True
    )


class ThreatIntelActorCampaignMapping(Base, TenantOwnedMixin):
    __tablename__ = "threat_intel_actor_campaign_mapping"

    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threat_intel_actors.actor_id", ondelete="CASCADE"), primary_key=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threat_intel_campaigns.campaign_id", ondelete="CASCADE"), primary_key=True
    )


class ThreatIntelHistory(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "threat_intel_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    ioc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threat_intel_iocs.ioc_id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)


# ==============================================================================
# SECURITY INTELLIGENCE GRAPH DOMAIN
# ==============================================================================

class SecurityIntelligenceNode(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "security_intelligence_nodes"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    node_fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    node_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="SET NULL"), nullable=True
    )


class SecurityIntelligenceEdge(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "security_intelligence_edges"

    edge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    edge_fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    edge_type: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="SET NULL"), nullable=True
    )


class SecurityIntelligenceGraphHistory(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "security_intelligence_graph_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    component_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)


class CyberRiskRecord(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "cyber_risk_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    risk_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    scenario_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    exposure_value: Mapped[float] = mapped_column(Numeric, nullable=False)
    single_loss_expectancy: Mapped[float] = mapped_column(Numeric, nullable=False)
    annualized_loss_expectancy: Mapped[float] = mapped_column(Numeric, nullable=False)
    inherent_risk_score: Mapped[float] = mapped_column(Numeric, nullable=False)
    residual_risk_score: Mapped[float] = mapped_column(Numeric, nullable=False)
    mitigation_effectiveness: Mapped[float] = mapped_column(Numeric, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="SET NULL"), nullable=True
    )

    @property
    def risk_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        UniqueConstraint("tenant_id", "risk_fingerprint", name="uq_cyber_risk_records_tenant_fingerprint"),
        Index("ix_cyber_risk_records_tenant", "tenant_id"),
        Index("ix_cyber_risk_records_tenant_status", "tenant_id", "status"),
        Index("ix_cyber_risk_records_tenant_created", "tenant_id", "created_at"),
    )


class CyberRiskScenario(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "cyber_risk_scenarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    scenario_type: Mapped[str] = mapped_column(String, nullable=False)
    frequency_label: Mapped[str] = mapped_column(String, nullable=False)
    impact_label: Mapped[str] = mapped_column(String, nullable=False)
    annualized_rate_of_occurrence: Mapped[float] = mapped_column(Numeric, nullable=False)
    exposure_factor: Mapped[float] = mapped_column(Numeric, nullable=False)
    expected_annual_loss: Mapped[float] = mapped_column(Numeric, nullable=False)

    __table_args__ = (
        Index("ix_cyber_risk_scenarios_tenant", "tenant_id"),
    )


class CyberRiskForecast(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "cyber_risk_forecasts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cyber_risk_records.id", ondelete="CASCADE"), nullable=False
    )
    quarter: Mapped[str] = mapped_column(String, nullable=False)
    projected_loss: Mapped[float] = mapped_column(Numeric, nullable=False)
    exposure_value: Mapped[float] = mapped_column(Numeric, nullable=False)

    __table_args__ = (
        Index("ix_cyber_risk_forecasts_tenant", "tenant_id"),
    )


class CyberRiskHistory(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "cyber_risk_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cyber_risk_records.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_cyber_risk_history_tenant", "tenant_id"),
    )


# ==============================================================================
# PHASE 1 PERSISTENT DOMAINS
# ==============================================================================

# 1. INCIDENT MANAGEMENT & INVESTIGATION
class Incident(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    incident_fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    owner: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    alert_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default="{}", nullable=False)
    asset_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default="{}", nullable=False)
    finding_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default="{}", nullable=False)
    recommendation_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default="{}", nullable=False)
    remediation_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default="{}", nullable=False)

    @property
    def incident_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_incidents_tenant", "tenant_id"),
        Index("ix_incidents_tenant_status", "tenant_id", "status"),
    )


class IncidentInvestigation(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "incident_investigations"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    analyst: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_incident_investigations_tenant", "tenant_id"),
        Index("ix_incident_investigations_incident", "incident_id"),
    )


class IncidentHistory(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "incident_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_incident_history_tenant", "tenant_id"),
        Index("ix_incident_history_incident", "incident_id"),
    )


class IncidentEvidence(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "incident_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_incident_evidence_tenant", "tenant_id"),
        Index("ix_incident_evidence_incident", "incident_id"),
    )


# 2. RISK ACCEPTANCE
class RiskAcceptance(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "risk_acceptances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    finding_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True
    )
    recommendation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    recommendation_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    approved_by: Mapped[str] = mapped_column(String, nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expiration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)

    @property
    def acceptance_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_risk_acceptances_tenant", "tenant_id"),
        Index("ix_risk_acceptances_asset", "asset_id"),
    )


# 3. REMEDIATION & SLA
class Remediation(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "remediations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    recommendation_fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    finding_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    owner: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    exception_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def remediation_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_remediations_tenant", "tenant_id"),
        Index("ix_remediations_fingerprint", "recommendation_fingerprint"),
    )


class RemediationHistory(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "remediation_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    remediation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("remediations.id", ondelete="CASCADE"), nullable=False
    )
    history_type: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (
        Index("ix_remediation_history_tenant", "tenant_id"),
        Index("ix_remediation_history_remediation", "remediation_id"),
    )


# ==============================================================================
# PHASE 2 PERSISTENT DOMAINS
# ==============================================================================

# 4. THREAT HUNTING & IOC SCAN
class Hunt(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "hunts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    hunt_fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    hunt_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="SET NULL"), nullable=True
    )
    related_entities: Mapped[list[dict]] = mapped_column(JSONB, server_default="[]", nullable=False)

    @property
    def hunt_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_hunts_tenant", "tenant_id"),
        Index("ix_hunts_tenant_status", "tenant_id", "status"),
    )


class HuntHypothesis(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "hunt_hypotheses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    hunt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hunts.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(String, nullable=False)

    @property
    def hypothesis_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_hunt_hypotheses_tenant", "tenant_id"),
        Index("ix_hunt_hypotheses_hunt", "hunt_id"),
    )


class HuntFinding(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "hunt_findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    hunt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hunts.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)

    @property
    def finding_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_hunt_findings_tenant", "tenant_id"),
        Index("ix_hunt_findings_hunt", "hunt_id"),
    )


class HuntHistory(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "hunt_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    hunt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hunts.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_hunt_history_tenant", "tenant_id"),
        Index("ix_hunt_history_hunt", "hunt_id"),
    )


# 5. UNIFIED SECURITY INTELLIGENCE FABRIC
class SecurityIntelligenceFabricNode(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "security_intelligence_fabric_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    node_fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="SET NULL"), nullable=True
    )
    confidence_weights: Mapped[Dict[str, float]] = mapped_column(JSONB, server_default="{}", nullable=False)
    target_links: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default="{}", nullable=False)

    @property
    def node_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_fabric_nodes_tenant", "tenant_id"),
        Index("ix_fabric_nodes_fingerprint", "node_fingerprint"),
    )


class SecurityIntelligenceFabricPropagation(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "security_intelligence_fabric_propagations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security_intelligence_fabric_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric, nullable=False)
    decay_factor: Mapped[float] = mapped_column(Numeric, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    @property
    def propagation_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_fabric_propagations_tenant", "tenant_id"),
        Index("ix_fabric_propagations_source", "source_node_id"),
    )


class SecurityIntelligenceFabricHistory(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "security_intelligence_fabric_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    fabric_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security_intelligence_fabric_nodes.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_fabric_history_tenant", "tenant_id"),
        Index("ix_fabric_history_fabric", "fabric_id"),
    )


# 6. SECURITY POSTURE
class SecurityPosture(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "security_postures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    posture_fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    posture_score: Mapped[float] = mapped_column(Numeric, nullable=False)
    risk_score: Mapped[float] = mapped_column(Numeric, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    owner: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    risk_source: Mapped[str] = mapped_column(String, nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="SET NULL"), nullable=True
    )

    @property
    def posture_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_security_postures_tenant", "tenant_id"),
        Index("ix_security_postures_asset", "asset_id"),
    )


class SecurityPostureHistory(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "security_posture_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    posture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security_postures.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_security_posture_history_tenant", "tenant_id"),
        Index("ix_security_posture_history_posture", "posture_id"),
    )


# ==============================================================================
# PHASE 3 PERSISTENT DOMAINS
# ==============================================================================

# 7. SECURITY DECISION
class SecurityDecision(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "security_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    decision_fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    decision_type: Mapped[str] = mapped_column(String, nullable=False)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    option_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="SET NULL"), nullable=True
    )
    tradeoff_matrix: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    impact_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    @property
    def decision_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_security_decisions_tenant", "tenant_id"),
        Index("ix_security_decisions_target", "target_entity_id"),
    )


class SecurityDecisionHistory(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "security_decision_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security_decisions.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_security_decision_history_tenant", "tenant_id"),
        Index("ix_security_decision_history_decision", "decision_id"),
    )


# 8. SECURITY PROGRAM
class SecurityProgram(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "security_programs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    program_fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    program_score: Mapped[float] = mapped_column(Numeric, nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="SET NULL"), nullable=True
    )

    @property
    def program_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_security_programs_tenant", "tenant_id"),
        Index("ix_security_programs_status", "tenant_id", "status"),
    )


class SecurityProgramObjective(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "security_program_objectives"

    objective_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security_programs.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    completion_percentage: Mapped[float] = mapped_column(Numeric, nullable=False)

    __table_args__ = (
        Index("ix_program_objectives_tenant", "tenant_id"),
        Index("ix_program_objectives_program", "program_id"),
    )


class SecurityProgramInitiative(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "security_program_initiatives"

    initiative_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security_programs.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    completion_percentage: Mapped[float] = mapped_column(Numeric, nullable=False)

    __table_args__ = (
        Index("ix_program_initiatives_tenant", "tenant_id"),
        Index("ix_program_initiatives_program", "program_id"),
    )


class SecurityProgramHistory(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "security_program_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("security_programs.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_security_program_history_tenant", "tenant_id"),
        Index("ix_security_program_history_program", "program_id"),
    )


# 9. PURPLE TEAM EMULATION
class PurpleTeamExercise(Base, TenantOwnedMixin, AuditMixin, VersionedMixin, SoftDeleteMixin):
    __tablename__ = "purple_team_exercises"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    exercise_fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    exercise_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    owner: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    scope_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scopes.id", ondelete="CASCADE"), nullable=False
    )

    @property
    def exercise_id(self) -> uuid.UUID:
        return self.id

    __table_args__ = (
        Index("ix_purple_team_exercises_tenant", "tenant_id"),
        Index("ix_purple_team_exercises_status", "tenant_id", "status"),
    )


class PurpleTeamValidation(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "purple_team_validations"

    validation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purple_team_exercises.id", ondelete="CASCADE"), nullable=False
    )
    technique_id: Mapped[str] = mapped_column(String, nullable=False)
    validation_status: Mapped[str] = mapped_column(String, nullable=False)
    expected_detection: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actual_detection: Mapped[bool] = mapped_column(Boolean, nullable=False)
    coverage_gap: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        Index("ix_purple_team_validations_tenant", "tenant_id"),
        Index("ix_purple_team_validations_exercise", "exercise_id"),
    )


class PurpleTeamFinding(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "purple_team_findings"

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purple_team_exercises.id", ondelete="CASCADE"), nullable=False
    )
    technique_id: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    gap_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_purple_team_findings_tenant", "tenant_id"),
        Index("ix_purple_team_findings_exercise", "exercise_id"),
    )


class PurpleTeamHistory(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "purple_team_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purple_team_exercises.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_purple_team_history_tenant", "tenant_id"),
        Index("ix_purple_team_history_exercise", "exercise_id"),
    )

