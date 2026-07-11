"""crit_07_rls_hardening

Revision ID: 7476d4d6195a
Revises: 8e2fe6d6496f
Create Date: 2026-07-11 04:36:47.639080

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7476d4d6195a'
down_revision: Union[str, None] = '8e2fe6d6496f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ALL_TENANT_TABLES = [
    "users", "scopes", "assets", "workflows", "plugins", "scan_runs",
    "findings", "finding_evidence", "finding_history", "reports", "artifacts",
    "audit_logs", "workflow_events", "plugin_events", "asset_relationships",
    "asset_history", "correlated_findings", "risk_scores", "asset_ports", "asset_services",
    "intelligence_events", "cyber_resilience_records", "recovery_objectives",
    "cyber_resilience_history", "soc_analytics_records", "soc_analyst_performance",
    "soc_operational_kpis", "soc_operational_kris", "soc_analytics_history",
    "grc_assessments", "grc_framework_controls", "grc_evidence", "grc_gaps",
    "grc_history", "security_knowledge_records", "security_knowledge_relationships",
    "security_knowledge_recommendations", "security_knowledge_history",
    "threat_intel_iocs", "threat_intel_actors", "threat_intel_campaigns",
    "threat_intel_ioc_actor_mappings", "threat_intel_ioc_campaign_mappings",
    "threat_intel_actor_campaign_mappings", "threat_intel_history",
    "security_intelligence_nodes", "security_intelligence_edges",
    "security_intelligence_graph_history", "cyber_risk_records",
    "cyber_risk_scenarios", "cyber_risk_forecasts", "cyber_risk_history",
    "incidents", "incident_investigations", "incident_history", "incident_evidence",
    "risk_acceptances", "remediations", "remediation_history", "hunts",
    "hunt_hypotheses", "hunt_findings", "hunt_history", "security_intelligence_fabric_nodes",
    "security_intelligence_fabric_propagations", "security_intelligence_fabric_history",
    "security_postures", "security_posture_history", "security_decisions",
    "security_decision_history", "security_programs", "security_program_objectives",
    "security_program_initiatives", "security_program_history", "purple_team_exercises",
    "purple_team_validations", "purple_team_findings", "purple_team_history"
]


def upgrade() -> None:
    for table in ALL_TENANT_TABLES:
        # Drop old policy
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        
        # Create strict policy with WITH CHECK
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
    for table in ALL_TENANT_TABLES:
        # Drop new policy
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        
        # Restore coalesce policy (old policy)
        op.execute(sa.text(f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (
                tenant_id = COALESCE(
                    NULLIF(current_setting('app.current_tenant', true), '')::uuid,
                    '00000000-0000-0000-0000-000000000000'::uuid
                )
            )
        """))
