"""findings sprint 8 updates

Revision ID: rev_002_findings_sprint8
Revises: rev_001_core_and_auth
Create Date: 2026-06-14 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "rev_002_findings_sprint8"
down_revision = "rev_001_core_and_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop findings (since it's a dev database and schema is completely restructured)
    op.execute("DROP TABLE findings CASCADE")
    op.create_table(
        "asset_ports",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("port", sa.BigInteger(), nullable=False),
        sa.Column("protocol", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "port", "protocol", name="uq_asset_port_protocol")
    )

    op.create_table(
        "asset_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_port_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_name", sa.String(), nullable=False),
        sa.Column("product", sa.String(), nullable=True),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("banner", sa.String(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_port_id"], ["asset_ports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_port_id", "service_name", name="uq_asset_port_service")
    )
    op.create_table(
        "findings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_port_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_service_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="open", nullable=False),
        sa.Column("template_id", sa.String(), nullable=False),
        sa.Column("template_name", sa.String(), nullable=False),
        sa.Column("source_plugin", sa.String(), nullable=False),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text(
                '\'{"cves": [], "cvss": null, "epss": null}\'::jsonb'
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["asset_port_id"], ["asset_ports.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["asset_service_id"], ["asset_services.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint"),
    )

    op.create_table(
        "finding_evidence",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_type", sa.String(), nullable=False),
        sa.Column("raw_request", sa.String(), nullable=True),
        sa.Column("raw_response", sa.String(), nullable=True),
        sa.Column("matched_at", sa.String(), nullable=True),
        sa.Column("matcher_name", sa.String(), nullable=True),
        sa.Column("matcher_value", sa.String(), nullable=True),
        sa.Column(
            "metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("evidence_hash", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_hash"),
    )

    op.create_table(
        "finding_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("change_type", sa.String(), nullable=False),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("finding_history")
    op.drop_table("finding_evidence")
    op.drop_table("findings")

    # Recreate the old findings table skeleton
    op.create_table(
        "findings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scanner", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fingerprint", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scan_run_id"], ["scan_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint"),
    )
