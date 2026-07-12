import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Scope


class CacheBootstrapService:
    @classmethod
    async def bootstrap_cache(cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None) -> None:
        """Cold start cache recovery. Clears and rebuilds advanced intelligence cache state."""
        from src.services.cyber_resilience_service import CyberResilienceService
        from src.services.security_operations_analytics_service import SecurityOperationsAnalyticsService
        from src.services.cyber_risk_quantification_service import CyberRiskQuantificationService
        from src.services.governance_risk_compliance_service import GovernanceRiskComplianceService
        from src.services.security_knowledge_service import SecurityKnowledgeService
        from src.services.threat_intelligence_service import ThreatIntelligenceService
        from src.services.security_intelligence_graph_service import SecurityIntelligenceGraphService
        from src.services.security_decision_service import SecurityDecisionService
        from src.services.autonomous_security_planning_service import AutonomousSecurityPlanningService
        from src.services.unified_security_intelligence_fabric_service import UnifiedSecurityIntelligenceFabricService

        # 1. Clear existing entries from cache storage adapters
        await CyberResilienceService.clear_resilience()
        await SecurityOperationsAnalyticsService.clear_analytics()
        CyberRiskQuantificationService.clear_risks()
        GovernanceRiskComplianceService.clear_assessments()
        SecurityKnowledgeService.clear_knowledge()
        ThreatIntelligenceService.clear_threats()
        SecurityIntelligenceGraphService.clear_graph()
        SecurityDecisionService.clear_decisions()
        AutonomousSecurityPlanningService.clear_plans()
        UnifiedSecurityIntelligenceFabricService.clear_fabric()

        from src.services.incident_service import IncidentService
        from src.services.risk_acceptance_service import RiskAcceptanceService
        from src.services.remediation_service import RemediationService
        from src.services.hunt_service import HuntService
        from src.services.attack_validation_service import AttackValidationService
        from src.services.security_posture_service import SecurityPostureService
        from src.services.security_program_service import SecurityProgramService
        from src.services.purple_team_service import PurpleTeamService

        IncidentService.clear_incidents()
        RiskAcceptanceService.clear_acceptances()
        RemediationService.clear_remediations()
        HuntService.clear_hunts()
        AttackValidationService.clear_validations()
        SecurityPostureService.clear_postures()
        SecurityProgramService.clear_programs()
        PurpleTeamService.clear_exercises()

        # 2. Get active scopes
        if scope_id:
            scopes = [scope_id]
        else:
            stmt = select(Scope.id).where(Scope.deleted_at.is_(None))
            res = await db.execute(stmt)
            scopes = [row[0] for row in res.all()]

        # 3. Synchronize GRC, Risk, Threat Intel, and Resilience services
        await CyberResilienceService.sync_resilience(db)
        await SecurityOperationsAnalyticsService.sync_analytics(db)
        await CyberRiskQuantificationService.sync_risks(db)
        await GovernanceRiskComplianceService.sync_assessments(db)
        await SecurityKnowledgeService.sync_knowledge(db)
        await ThreatIntelligenceService.sync_threats(db)
        from src.services.graph_bootstrap_service import GraphBootstrapService
        await GraphBootstrapService.bootstrap()

        await IncidentService.bootstrap(db)
        await RiskAcceptanceService.bootstrap(db)
        await RemediationService.bootstrap(db)
        await HuntService.bootstrap(db)
        await AttackValidationService.bootstrap(db)
        await SecurityPostureService.bootstrap(db)
        await SecurityProgramService.bootstrap(db)
        await PurpleTeamService.bootstrap(db)
        await SecurityDecisionService.bootstrap(db)
        await UnifiedSecurityIntelligenceFabricService.bootstrap(db)

        # 4. Recalculate derived scores (Calculations and playbooks)
        from src.services.analyst_performance_service import AnalystPerformanceService
        from src.services.operational_kpi_service import OperationalKPIService
        from src.services.operational_kri_service import OperationalKRIService
        from src.services.loss_expectancy_service import LossExpectancyService
        from src.services.residual_risk_service import ResidualRiskService
        from src.services.risk_forecast_service import RiskForecastService
        from src.services.risk_trend_service import RiskTrendService
        from src.services.compliance_scoring_service import ComplianceScoringService
        from src.services.compliance_gap_service import ComplianceGapService
        from src.services.knowledge_relationship_service import KnowledgeRelationshipService
        from src.services.knowledge_relevance_service import KnowledgeRelevanceService
        from src.services.knowledge_recommendation_service import KnowledgeRecommendationService
        from src.services.threat_intel_fusion_service import ThreatIntelFusionService

        # Run derived SOC analytics
        await AnalystPerformanceService.calculate()
        await OperationalKPIService.calculate()
        await OperationalKRIService.calculate()

        # Run GRC scoring and mapping
        ComplianceScoringService.calculate()
        ComplianceGapService.calculate()
        await GovernanceRiskComplianceService.recalculate_assessments()

        # Run knowledge relationships
        KnowledgeRelationshipService.calculate()
        KnowledgeRelevanceService.calculate()
        KnowledgeRecommendationService.calculate()
        await SecurityKnowledgeService.recalculate_knowledge()

        # Run Threat Intel fusion
        from src.domain.entities.threat_intel import ThreatIntelStatus
        for threat in ThreatIntelligenceService.get_all_threats():
            if threat.status == ThreatIntelStatus.ARCHIVED:
                continue
            score = ThreatIntelFusionService.calculate_fusion_score(threat.value, threat.indicator_type.value)
            await ThreatIntelligenceService.fuse_threat(threat.threat_intel_id, score)
        ThreatIntelFusionService.calculate()

        # Run FAIR risk quantification
        LossExpectancyService.calculate()
        ResidualRiskService.calculate()
        RiskForecastService.calculate()
        RiskTrendService.calculate()

        # 5. Rebuild Graph Topology
        await SecurityIntelligenceGraphService.rebuild_graph_topology(db)
        from src.services.graph_correlation_service import GraphCorrelationService
        await GraphCorrelationService.recalculate_cross_domain_links()

        # 6. Rebuild Decision Recommendations & tradeoff matrices
        await SecurityDecisionService.sync_decision_recommendations(db)
        from src.services.decision_tradeoff_service import DecisionTradeoffService
        DecisionTradeoffService.calculate()

        # 7. Rebuild Planning milestones & sequences
        await AutonomousSecurityPlanningService.sync_plans(db)
        from src.services.planning_optimization_service import PlanningOptimizationService
        PlanningOptimizationService.optimize_sequences()

        # 8. Rebuild Fabric propagation confidence nodes
        await UnifiedSecurityIntelligenceFabricService.sync_fabric_state(db)
        from src.services.intelligence_propagation_service import IntelligencePropagationService
        IntelligencePropagationService.process_propagation()

        # 9. Rebuild Snapshots and Drift caches
        from src.services.cyber_resilience_snapshot_service import CyberResilienceSnapshotService
        from src.services.soc_snapshot_service import SOCSnapshotService
        from src.services.risk_quantification_snapshot_service import RiskQuantificationSnapshotService
        from src.services.compliance_snapshot_service import ComplianceSnapshotService
        from src.services.knowledge_snapshot_service import KnowledgeSnapshotService
        from src.services.threat_intel_snapshot_service import ThreatIntelSnapshotService
        from src.services.graph_snapshot_service import GraphSnapshotService
        from src.services.decision_snapshot_service import DecisionSnapshotService
        from src.services.planning_snapshot_service import PlanningSnapshotService
        from src.services.fabric_snapshot_service import FabricSnapshotService

        for s_id in scopes:
            await CyberResilienceSnapshotService.generate_snapshot(db, s_id)
            await SOCSnapshotService.generate_snapshot(db, s_id)
            await RiskQuantificationSnapshotService.generate_snapshot(db, s_id)
            await ComplianceSnapshotService.generate_snapshot(db, s_id)
            await KnowledgeSnapshotService.generate_snapshot(db, s_id)
            await ThreatIntelSnapshotService.generate_snapshot(db, s_id)
            await GraphSnapshotService.generate_snapshot(db, s_id)
            await DecisionSnapshotService.generate_snapshot(db, s_id)
            await PlanningSnapshotService.generate_snapshot(db, s_id)
            await FabricSnapshotService.generate_snapshot(db, s_id)
