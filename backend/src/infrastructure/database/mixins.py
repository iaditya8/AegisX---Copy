import uuid
from datetime import datetime
from sqlalchemy import UUID, DateTime, ForeignKey, text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, declarative_mixin


@declarative_mixin
class TenantOwnedMixin:
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )


@declarative_mixin
class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


@declarative_mixin
class VersionedMixin:
    version: Mapped[int] = mapped_column(
        Integer, server_default="1", nullable=False
    )

    __mapper_args__ = {
        "version_id_col": version
    }


@declarative_mixin
class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
