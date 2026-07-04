"""create partitioned event store table

Revision ID: rev_004_event_store
Revises: rev_003_multi_tenancy
Create Date: 2026-07-04 01:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "rev_004_event_store"
down_revision = "rev_003_multi_tenancy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create partitioned table
    op.execute(
        sa.text(
            """
            CREATE TABLE intelligence_events (
                id UUID NOT NULL DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                domain VARCHAR NOT NULL,
                entity_id UUID NOT NULL,
                actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
                event_type VARCHAR NOT NULL,
                payload JSONB NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'pending',
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                PRIMARY KEY (id, timestamp)
            ) PARTITION BY RANGE (timestamp)
            """
        )
    )

    # 2. Create default partition
    op.execute(
        sa.text(
            """
            CREATE TABLE intelligence_events_default PARTITION OF intelligence_events DEFAULT
            """
        )
    )

    # 3. Enable RLS and add tenant isolation policy
    op.execute(sa.text("ALTER TABLE intelligence_events ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation ON intelligence_events
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            """
        )
    )


def downgrade() -> None:
    # Drop parent table (cascades and drops partitions as well)
    op.execute(sa.text("DROP TABLE IF EXISTS intelligence_events CASCADE"))
