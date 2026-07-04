"""multi tenancy setup

Revision ID: rev_003_multi_tenancy
Revises: rev_002_findings_sprint8
Create Date: 2026-07-04 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "rev_003_multi_tenancy"
down_revision = "rev_002_findings_sprint8"
branch_labels = None
depends_on = None

TABLES_TO_TENANTIZE = [
    "users",
    "scopes",
    "assets",
    "workflows",
    "plugins",
    "scan_runs",
    "findings",
    "finding_evidence",
    "finding_history",
    "reports",
    "artifacts",
    "audit_logs",
    "workflow_events",
    "plugin_events",
    "asset_relationships",
    "asset_history",
    "correlated_findings",
    "risk_scores",
    "asset_ports",
    "asset_services",
]


def upgrade() -> None:
    # 1. Create tenants table
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # 2. Insert a default tenant
    default_tenant_id = "00000000-0000-0000-0000-000000000000"
    op.execute(
        sa.text(
            f"INSERT INTO tenants (id, name) VALUES ('{default_tenant_id}', 'Default Tenant') ON CONFLICT DO NOTHING"
        )
    )

    # 3. Add tenant_id to each existing table, set to default, make non-nullable, and add FK + RLS
    for table in TABLES_TO_TENANTIZE:
        # Add column as nullable first
        op.add_column(
            table,
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True)
        )
        
        # Populate with default tenant ID
        op.execute(
            sa.text(
                f"UPDATE {table} SET tenant_id = '{default_tenant_id}' WHERE tenant_id IS NULL"
            )
        )
        
        # Make it non-nullable
        op.alter_column(table, "tenant_id", nullable=False)
        
        # Create Foreign Key Constraint
        op.create_foreign_key(
            f"fk_{table}_tenant_id",
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE"
        )

        # Enable and Force RLS on the table
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

        # Create tenant isolation policy
        op.execute(
            sa.text(
                f"""
                CREATE POLICY tenant_isolation ON {table}
                USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, '00000000-0000-0000-0000-000000000000'::uuid))
                """
            )
        )


    # 4. Create non-superuser role for RLS enforcement
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'aegisx_user') THEN
                    CREATE ROLE aegisx_user WITH LOGIN PASSWORD 'aegisx_password';
                END IF;
            END
            $$;
            """
        )
    )
    op.execute(sa.text("GRANT CONNECT ON DATABASE aegisx TO aegisx_user"))
    op.execute(sa.text("GRANT USAGE ON SCHEMA public TO aegisx_user"))
    op.execute(sa.text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aegisx_user"))
    op.execute(sa.text("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO aegisx_user"))
    op.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aegisx_user"
        )
    )
    op.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO aegisx_user"
        )
    )


def downgrade() -> None:
    # Drop role and revoke privileges cleanly
    op.execute(sa.text("DROP OWNED BY aegisx_user CASCADE"))
    op.execute(sa.text("DROP ROLE IF EXISTS aegisx_user"))

    for table in TABLES_TO_TENANTIZE:
        # Drop RLS policy, disable force, and disable RLS
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

        # Drop Foreign Key Constraint
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")
        
        # Drop column
        op.drop_column(table, "tenant_id")

    # Drop tenants table
    op.drop_table("tenants")
