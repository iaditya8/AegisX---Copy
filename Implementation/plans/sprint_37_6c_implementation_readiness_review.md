# AegisX Sprint 37.6C — Implementation Readiness Review

**Objective:** Convert the finalized ADR and Implementation Plan into an executable, zero-guesswork work package for engineering squads.

## Issue Resolution & Corrections from 37.6B
1. **Graph Architecture Contradiction:** Resolved. The Graph is strictly a **Projection Layer**. `sig_nodes` will NOT contain 20+ explicit foreign keys. It will contain `node_id`, `node_type`, and `entity_id` (UUID). Referential integrity is guaranteed upstream by the domain tables; the graph is populated solely via the Event Outbox.
2. **JSONB Regression:** Resolved. `tradeoffs`, `roadmaps`, and `weights` are now strictly defined as relational tables. JSONB is reserved purely for display-only attributes (e.g., audit log payloads).
3. **Time Estimates:** Corrected. The implementation backlog is now scoped for a **4–6 week** timeline for a dedicated engineering team, accounting for the heavy refactoring of 308 services.

---

## Deliverable 1: Complete Model Inventory

| Domain | Model (Entity) | PostgreSQL Table | Alembic Migration | Owner |
| :--- | :--- | :--- | :--- | :--- |
| **Core** | `Tenant` | `tenants` | `rev_003_multi_tenancy` | Platform |
| **Audit** | `IntelligenceEvent` | `intelligence_events` (Partitioned) | `rev_004_event_store` | Platform |
| **Resilience** | `CyberResilienceRecord` | `cyber_resilience_records` | `rev_005_base_intel` | Resilience Squad |
| **Resilience** | `RecoveryObjective` | `cyber_resilience_objectives` | `rev_005_base_intel` | Resilience Squad |
| **SOC** | `AnalyticsRecord` | `soc_analytics_records` | `rev_005_base_intel` | SOC Squad |
| **SOC** | `AnalystPerformance` | `soc_analyst_performance` | `rev_005_base_intel` | SOC Squad |
| **SOC** | `OperationalKPI` | `soc_operational_kpis` | `rev_005_base_intel` | SOC Squad |
| **SOC** | `OperationalKRI` | `soc_operational_kris` | `rev_005_base_intel` | SOC Squad |
| **Risk** | `CyberRiskRecord` | `cyber_risk_records` | `rev_006_cross_domain` | Risk Squad |
| **Risk** | `RiskScenario` | `cyber_risk_scenarios` *(Normalized)* | `rev_006_cross_domain` | Risk Squad |
| **Risk** | `RiskForecast` | `cyber_risk_forecasts` | `rev_006_cross_domain` | Risk Squad |
| **GRC** | `ComplianceAssessment`| `grc_assessments` | `rev_005_base_intel` | GRC Squad |
| **GRC** | `FrameworkControl` | `grc_framework_controls` | `rev_005_base_intel` | GRC Squad |
| **GRC** | `ComplianceEvidence` | `grc_evidence` | `rev_005_base_intel` | GRC Squad |
| **GRC** | `ComplianceGap` | `grc_gaps` | `rev_005_base_intel` | GRC Squad |
| **Knowledge** | `KnowledgeRecord` | `security_knowledge_records` | `rev_005_base_intel` | Threat Squad |
| **Threat** | `IOCRecord` | `threat_intel_iocs` | `rev_005_base_intel` | Threat Squad |
| **Threat** | `ThreatActor` | `threat_intel_actors` | `rev_005_base_intel` | Threat Squad |
| **Threat** | `Campaign` | `threat_intel_campaigns` | `rev_005_base_intel` | Threat Squad |
| **Decisions** | `SecurityDecision` | `security_decisions` | `rev_006_cross_domain` | Decision Squad |
| **Decisions** | `DecisionTradeoff` | `decision_tradeoffs` *(Normalized)* | `rev_006_cross_domain` | Decision Squad |
| **Planning** | `AutonomousPlan` | `autonomous_plans` | `rev_006_cross_domain` | Plan Squad |
| **Planning** | `PlanRoadmap` | `autonomous_plan_roadmaps` *(Normalized)*| `rev_006_cross_domain` | Plan Squad |
| **Fabric** | `FabricNode` | `fabric_nodes` | `rev_007_graph_fabric` | AI/Platform Squad|
| **Fabric** | `FabricWeight` | `fabric_node_weights` *(Normalized)* | `rev_007_graph_fabric` | AI/Platform Squad|
| **Graph** | `GraphNode` | `sig_nodes` (Projection) | `rev_007_graph_fabric` | AI/Platform Squad|
| **Graph** | `GraphEdge` | `sig_edges` (Projection) | `rev_007_graph_fabric` | AI/Platform Squad|

---

## Deliverable 2: Repository Inventory

| Repository | Aggregate Root | Key Service Dependencies |
| :--- | :--- | :--- |
| `TenantRepository` | `Tenant` | `AuthService`, `ScopeService` |
| `EventRepository` | `IntelligenceEvent` | `*Service` (All publishers), `WorkflowEventService` |
| `CyberResilienceRepository` | `CyberResilienceRecord` | `CyberResilienceService`, `ResilienceScoringService` |
| `SOCAnalyticsRepository` | `AnalyticsRecord` | `SecurityOperationsAnalyticsService`, `QueueAnalyticsService` |
| `SOCMetricsRepository` | `OperationalKPI` | `KPIService`, `KRIService`, `OperationalKPIService` |
| `CyberRiskRepository` | `CyberRiskRecord` | `CyberRiskQuantificationService`, `RiskScoringService` |
| `RiskScenarioRepository` | `RiskScenario` | `RiskForecastService`, `LossExpectancyService` |
| `GRCAssessmentRepository` | `ComplianceAssessment` | `GovernanceRiskComplianceService`, `AuditReadinessService` |
| `GRCControlRepository` | `FrameworkControl` | `ControlValidationService`, `ComplianceMappingService` |
| `SecurityKnowledgeRepository` | `KnowledgeRecord` | `SecurityKnowledgeService`, `KnowledgeRelevanceService` |
| `ThreatIntelRepository` | `IOCRecord` | `ThreatIntelligenceService`, `IOCService`, `ThreatActorService` |
| `SecurityDecisionRepository` | `SecurityDecision` | `SecurityDecisionService`, `DecisionTradeoffService` |
| `AutonomousPlanRepository` | `AutonomousPlan` | `AutonomousSecurityPlanningService`, `PlanningOptimizationService` |
| `FabricRepository` | `FabricNode` | `UnifiedSecurityIntelligenceFabricService`, `IntelligencePropagationService` |
| **[CQRS Read-Only Repositories]** | | |
| `ExecutiveDashboardReader` | (Materialized Views) | `ExecutiveReportingService`, `ExecutiveHeatmapService` |
| `GraphProjectionReader` | `GraphNode` | `SecurityIntelligenceGraphService`, `GraphCorrelationService` |

---

## Deliverable 3: Service Impact Matrix (308 Services)

*Note: Services are grouped by refactoring effort based on their architectural patterns.*

**Category A: Unchanged (or highly minimal adjustments)** (Est. 40 Services)
*Primarily static registries and stateless helper utilities.*
- **Examples:** `alert_severity_registry.py`, `attack_registry.py`, `compliance_framework_registry.py`, `ai_prompt_builder.py`, `ai_response_validator.py`, `threat_source_registry.py`, `risk_impact_registry.py`.

**Category B: Minor Refactor (Read-Heavy / Cache Dependent)** (Est. 85 Services)
*Services that currently read from `CacheDict` but don't manage complex aggregates. Refactor involves swapping cache reads for Repository reads.*
- **Examples:** `asset_copilot_service.py`, `finding_copilot_service.py`, `ai_context_builder.py`, `dashboard_service.py`, `report_cache_service.py`, `compliance_scoring_service.py`, `risk_scoring_service.py`, `threat_intel_fusion_service.py`, `knowledge_recommendation_service.py`.

**Category C: Major Refactor (CRUD & Aggregates)** (Est. 120 Services)
*The core domain managers. Must be fully rewritten to use `UnitOfWork`, transaction boundaries, Repositories, and the Event Outbox.*
- **Examples:** `cyber_resilience_service.py`, `security_operations_analytics_service.py`, `cyber_risk_quantification_service.py`, `governance_risk_compliance_service.py`, `threat_intelligence_service.py`, `security_knowledge_service.py`, `security_decision_service.py`, `autonomous_security_planning_service.py`, `incident_service.py`, `case_service.py`, `investigation_service.py`.

**Category D: Major Refactor (History & CQRS Reprojection)** (Est. 63 Services)
*Services that currently append to in-memory lists for history/drift/snapshots. Must be rewritten entirely to query the `intelligence_events` central log or Materialized Views.*
- **Examples:** `*_history_service.py` (e.g., `grc_history_service.py`, `decision_history_service.py`), `*_snapshot_service.py` (e.g., `risk_quantification_snapshot_service.py`, `soc_snapshot_service.py`), `*_drift_service.py` (e.g., `compliance_drift_service.py`).

---

## Deliverable 4: Migration Dependency Map

| Migration File | Tables Created | FK Dependencies (Must exist prior) | Rollback Dependencies |
| :--- | :--- | :--- | :--- |
| `rev_003_multi_tenancy` | `tenants` | None | Drops `tenants`. Must run first on rollback. |
| `rev_004_event_store` | `intelligence_events` | `tenants(id)` | Drops `intelligence_events`. |
| `rev_005_base_intel` | `grc_assessments`, `cyber_resilience_records`, `soc_analytics_records`, `threat_intel_iocs`, `security_knowledge_records`, etc. | `tenants(id)`, `scopes(id)` | Drops all base tables. |
| `rev_006_cross_domain` | `cyber_risk_records`, `cyber_risk_scenarios`, `security_decisions`, `decision_tradeoffs`, `autonomous_plans`, `autonomous_plan_roadmaps` | `tenants(id)`, `scopes(id)`, base intel tables (for target entities). | Drops all cross-domain tables. |
| `rev_007_graph_fabric` | `sig_nodes`, `sig_edges`, `fabric_nodes`, `fabric_node_weights` | `tenants(id)` (No explicit domain FKs; Projection Layer) | Drops projection tables. |

*Ordering is strictly 003 -> 007. Rollback is strictly 007 -> 003.*

---

## Deliverable 5: Implementation Backlog (4-6 Weeks)

### Epic 1: Multi-Tenancy & Persistence Foundations
*   **Feature 1.1:** Core Tenant Models & RLS
    *   *Task:* Create `Tenant` SQLAlchemy model and migration (`rev_003`).
    *   *Task:* Apply PostgreSQL RLS policies for `tenant_id`.
    *   *AC:* Unit tests prove Tenant A cannot read Tenant B's data via SQL injection or direct query.
*   **Feature 1.2:** Central Event Outbox
    *   *Task:* Create `intelligence_events` partitioned table and migration (`rev_004`).
    *   *Task:* Implement `EventRepository`.
    *   *AC:* Events successfully partition by month automatically.

### Epic 2: Domain Modeling & Repositories
*   **Feature 2.1:** Base Intelligence Relational Models
    *   *Task:* Build GRC, Resilience, Threat, Knowledge SQLAlchemy models and migrations (`rev_005`).
    *   *Task:* Build strictly relational Normalized tables for previously JSONB structures (e.g., Tradeoffs, Roadmaps).
*   **Feature 2.2:** Core Repositories & Unit of Work
    *   *Task:* Implement `UnitOfWork` context manager.
    *   *Task:* Implement Repositories for Base Intelligence.
    *   *AC:* Repositories successfully map DB models to domain Pydantic entities within a single transaction.

### Epic 3: 308-Service Refactoring Wave
*   **Feature 3.1:** Category C Refactor (Core CRUD)
    *   *Task:* Strip `CacheDict` from `threat_intelligence_service.py` -> Use `ThreatRepository` + UoW.
    *   *Task:* Implement outbox publishing within UoW for state changes.
    *   *(Repeat for all 120 major domain services)*.
*   **Feature 3.2:** Category B Refactor (Reads & AI)
    *   *Task:* Refactor Copilot and Context builders to query Repositories instead of CacheDict.

### Epic 4: CQRS, History, and Graph Projections
*   **Feature 4.1:** History Service Refactor (Category D)
    *   *Task:* Rewrite all `*_history_service.py` modules to query the `intelligence_events` table natively.
*   **Feature 4.2:** Graph Projection Handlers
    *   *Task:* Implement Celery workers that consume `intelligence_events` and insert/update rows in `sig_nodes` and `sig_edges`.
    *   *Task:* Create Materialized Views for `ExecutiveDashboardReader`.
    *   *AC:* Creating a Risk record automatically triggers an outbox event that creates a Risk node in the Graph Projection.

### Epic 5: Validation & Deployment Cutover
*   **Feature 5.1:** E2E Integration Testing
    *   *Task:* Run full platform test suite against PostgreSQL testcontainers.
*   **Feature 5.2:** Data Migration (If applicable)
    *   *Task:* Write Python extraction script to dump active `CacheDict` memory state (if any persisted Redis instances exist) to JSONL.
    *   *Task:* Write seeder script to populate new PostgreSQL tables.
    *   *AC:* Zero data loss during maintenance window.
