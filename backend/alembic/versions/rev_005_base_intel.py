"""create base intelligence tables

Revision ID: rev_005_base_intel
Revises: rev_004_event_store
Create Date: 2026-07-04 02:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "rev_005_base_intel"
down_revision = "rev_004_event_store"
branch_labels = None
depends_on = None

NEW_TABLES = [
    "cyber_resilience_records",
    "cyber_resilience_objectives",
    "cyber_resilience_history",
    "soc_analytics_records",
    "soc_analyst_performance",
    "soc_operational_kpis",
    "soc_operational_kris",
    "soc_analytics_history",
    "grc_assessments",
    "grc_framework_controls",
    "grc_evidence",
    "grc_gaps",
    "grc_history",
    "security_knowledge_records",
    "security_knowledge_relationships",
    "security_knowledge_recommendations",
    "security_knowledge_history",
    "threat_intel_iocs",
    "threat_intel_actors",
    "threat_intel_campaigns",
    "threat_intel_ioc_actor_mapping",
    "threat_intel_ioc_campaign_mapping",
    "threat_intel_actor_campaign_mapping",
    "threat_intel_history",
]


def upgrade() -> None:
    # 1. Cyber Resilience
    op.create_table(
        "cyber_resilience_records",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resilience_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("resilience_fingerprint", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("service_name", sa.String(), nullable=False),
        sa.Column("service_criticality", sa.String(), nullable=False),
        sa.Column("resilience_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("readiness_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("recovery_confidence_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scope_id"], ["scopes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("resilience_id"),
        sa.UniqueConstraint("resilience_fingerprint"),
    )

    op.create_table(
        "cyber_resilience_objectives",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("objective_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("resilience_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("objective_type", sa.String(), nullable=False),
        sa.Column("target_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("current_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("compliance_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resilience_id"], ["cyber_resilience_records.resilience_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("objective_id"),
    )

    op.create_table(
        "cyber_resilience_history",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("resilience_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resilience_id"], ["cyber_resilience_records.resilience_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. SOC Analytics
    op.create_table(
        "soc_analytics_records",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analytics_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("analytics_fingerprint", sa.String(), nullable=False),
        sa.Column("analytics_name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scope_id"], ["scopes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("analytics_id"),
        sa.UniqueConstraint("analytics_fingerprint"),
    )

    op.create_table(
        "soc_analyst_performance",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analyst_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("analyst_name", sa.String(), nullable=False),
        sa.Column("alerts_handled", sa.Integer(), nullable=False),
        sa.Column("incidents_handled", sa.Integer(), nullable=False),
        sa.Column("cases_handled", sa.Integer(), nullable=False),
        sa.Column("average_response_time", sa.Numeric(10, 2), nullable=False),
        sa.Column("average_resolution_time", sa.Numeric(10, 2), nullable=False),
        sa.Column("analyst_score", sa.Numeric(5, 2), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("analyst_id"),
    )

    op.create_table(
        "soc_operational_kpis",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kpi_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kpi_name", sa.String(), nullable=False),
        sa.Column("current_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("target_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("kpi_id"),
    )

    op.create_table(
        "soc_operational_kris",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kri_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kri_name", sa.String(), nullable=False),
        sa.Column("current_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("threshold_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("kri_id"),
    )

    op.create_table(
        "soc_analytics_history",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("analytics_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analytics_id"], ["soc_analytics_records.analytics_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. GRC Intelligence
    op.create_table(
        "grc_assessments",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("assessment_fingerprint", sa.String(), nullable=False),
        sa.Column("framework_type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("compliance_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("framework_coverage", sa.Numeric(5, 2), nullable=False),
        sa.Column("control_coverage", sa.Numeric(5, 2), nullable=False),
        sa.Column("evidence_completeness", sa.Numeric(5, 2), nullable=False),
        sa.Column("audit_readiness", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scope_id"], ["scopes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("assessment_id"),
        sa.UniqueConstraint("assessment_fingerprint"),
    )

    op.create_table(
        "grc_framework_controls",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("control_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("control_name", sa.String(), nullable=False),
        sa.Column("framework_type", sa.String(), nullable=False),
        sa.Column("requirement_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["grc_assessments.assessment_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("control_id"),
    )

    op.create_table(
        "grc_evidence",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("file_hash", sa.String(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["grc_assessments.assessment_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("evidence_id"),
        sa.UniqueConstraint("file_hash"),
    )

    op.create_table(
        "grc_gaps",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gap_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gap_type", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("remediation_plan", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["grc_assessments.assessment_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("gap_id"),
    )

    op.create_table(
        "grc_history",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["grc_assessments.assessment_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 4. Security Knowledge
    op.create_table(
        "security_knowledge_records",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("knowledge_fingerprint", sa.String(), nullable=False),
        sa.Column("knowledge_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("relevance_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scope_id"], ["scopes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("knowledge_id"),
        sa.UniqueConstraint("knowledge_fingerprint"),
    )

    op.create_table(
        "security_knowledge_relationships",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("relationship_type", sa.String(), nullable=False),
        sa.Column("weight", sa.Numeric(5, 2), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("relationship_id"),
    )

    op.create_table(
        "security_knowledge_recommendations",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("knowledge_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_id"], ["security_knowledge_records.knowledge_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("recommendation_id"),
    )

    op.create_table(
        "security_knowledge_history",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("knowledge_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_id"], ["security_knowledge_records.knowledge_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 5. Threat Intelligence
    op.create_table(
        "threat_intel_iocs",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ioc_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ioc_fingerprint", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("ioc_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("reputation", sa.Integer(), nullable=False),
        sa.Column("feed_type", sa.String(), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scope_id"], ["scopes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("ioc_id"),
        sa.UniqueConstraint("ioc_fingerprint"),
    )

    op.create_table(
        "threat_intel_actors",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("actor_id"),
    )

    op.create_table(
        "threat_intel_campaigns",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("campaign_id"),
    )

    op.create_table(
        "threat_intel_ioc_actor_mapping",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ioc_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ioc_id"], ["threat_intel_iocs.ioc_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["threat_intel_actors.actor_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ioc_id", "actor_id"),
    )

    op.create_table(
        "threat_intel_ioc_campaign_mapping",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ioc_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ioc_id"], ["threat_intel_iocs.ioc_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["threat_intel_campaigns.campaign_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ioc_id", "campaign_id"),
    )

    op.create_table(
        "threat_intel_actor_campaign_mapping",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["threat_intel_actors.actor_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["threat_intel_campaigns.campaign_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("actor_id", "campaign_id"),
    )

    op.create_table(
        "threat_intel_history",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ioc_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ioc_id"], ["threat_intel_iocs.ioc_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 6. Apply RLS & Force RLS to all new tables
    for table in NEW_TABLES:
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"""
                CREATE POLICY tenant_isolation ON {table}
                USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant', true), '')::uuid, '00000000-0000-0000-0000-000000000000'::uuid))
                """
            )
        )


def downgrade() -> None:
    # Drop all new tables
    for table in reversed(NEW_TABLES):
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"DROP TABLE IF EXISTS {table} CASCADE"))
