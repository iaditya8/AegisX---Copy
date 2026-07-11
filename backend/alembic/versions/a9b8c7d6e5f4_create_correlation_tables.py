"""create_correlation_tables

Revision ID: a9b8c7d6e5f4
Revises: 7476d4d6195a
Create Date: 2026-07-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, None] = '7476d4d6195a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_TABLES = [
    "correlation_rules",
    "correlation_clusters",
    "correlation_cluster_signals",
    "correlation_history",
    "correlation_rule_matches",
]

def upgrade() -> None:
    # 1. correlation_rules
    op.create_table(
        'correlation_rules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('condition_expression', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('priority_level', sa.String(length=50), nullable=False),
        sa.Column('rule_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_correlation_rules_tenant', 'correlation_rules', ['tenant_id'])

    # 2. correlation_clusters
    op.create_table(
        'correlation_clusters',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('asset_id', sa.UUID(), nullable=False),
        sa.Column('unified_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('score_breakdown_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='open'),
        sa.Column('fingerprint', sa.String(length=255), nullable=False),
        sa.Column('associated_incident_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['associated_incident_id'], ['incidents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'fingerprint', name='uq_cluster_tenant_fingerprint')
    )
    op.create_index('ix_correlation_clusters_tenant_asset', 'correlation_clusters', ['tenant_id', 'asset_id'])
    op.create_index('ix_correlation_clusters_incident', 'correlation_clusters', ['associated_incident_id'])

    # 3. correlation_cluster_signals
    op.create_table(
        'correlation_cluster_signals',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('cluster_id', sa.UUID(), nullable=False),
        sa.Column('signal_type', sa.String(length=100), nullable=False),
        sa.Column('signal_id', sa.UUID(), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cluster_id'], ['correlation_clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cluster_id', 'signal_type', 'signal_id', name='uq_cluster_signal')
    )
    op.create_index('ix_correlation_signals_lookup', 'correlation_cluster_signals', ['signal_type', 'signal_id'])
    op.create_index('ix_correlation_signals_tenant', 'correlation_cluster_signals', ['tenant_id'])

    # 4. correlation_history
    op.create_table(
        'correlation_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('cluster_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('details_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cluster_id'], ['correlation_clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_correlation_history_cluster', 'correlation_history', ['cluster_id'])
    op.create_index('ix_correlation_history_tenant', 'correlation_history', ['tenant_id'])

    # 5. correlation_rule_matches
    op.create_table(
        'correlation_rule_matches',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('rule_id', sa.UUID(), nullable=False),
        sa.Column('rule_version_used', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.UUID(), nullable=False),
        sa.Column('matched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('evidence_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rule_id'], ['correlation_rules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cluster_id'], ['correlation_clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_correlation_rule_matches_rule', 'correlation_rule_matches', ['rule_id'])
    op.create_index('ix_correlation_rule_matches_cluster', 'correlation_rule_matches', ['cluster_id'])
    op.create_index('ix_correlation_rule_matches_tenant', 'correlation_rule_matches', ['tenant_id'])

    # Enable RLS policies
    for table in NEW_TABLES:
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
            )
        """))


def downgrade() -> None:
    for table in reversed(NEW_TABLES):
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        op.drop_table(table)
