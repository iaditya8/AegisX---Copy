# AegisX Sprint 37.6: Intelligence Persistence Architecture Program

**Objective:** Design a production-grade persistence layer to eliminate CRIT-06 (In-Memory State Data Loss) for all advanced intelligence domains introduced in Sprints 24–37.5.

**Status:** Architecture Specification
**Author:** Principal Architecture Team

---

## 1. Domain Aggregates and PostgreSQL Table Design

To persist the complex objects currently stored in Python memory, we will introduce the following SQLAlchemy models and corresponding PostgreSQL tables. All tables will use `UUID(as_uuid=True)` for primary keys with `server_default=text("gen_random_uuid()")`.

### 1.1 Cyber Resilience (`cyber_resilience_records`)
- **`cyber_resilience_records`**: `resilience_id` (PK), `resilience_fingerprint` (UQ), `title`, `description`, `service_name`, `service_criticality`, `resilience_score`, `readiness_score`, `recovery_confidence_score`, `status`, `scope_id` (FK to `scopes`), timestamps.
- **`cyber_resilience_objectives`**: `objective_id` (PK), `resilience_id` (FK), `objective_type`, `target_value`, `current_value`, `compliance_percentage`, timestamps.
- **`cyber_resilience_history`**: `id` (PK), `resilience_id` (FK), `timestamp`, `event_type`, `details` (JSONB).

### 1.2 SOC Analytics (`soc_analytics_records`)
- **`soc_analytics_records`**: `analytics_id` (PK), `analytics_fingerprint` (UQ), `analytics_name`, `status`, `scope_id` (FK), timestamps.
- **`soc_analyst_performance`**: `analyst_id` (PK), `analyst_name`, `alerts_handled`, `incidents_handled`, `cases_handled`, `average_response_time`, `average_resolution_time`, `analyst_score`.
- **`soc_operational_kpis`**: `kpi_id` (PK), `kpi_name`, `current_value`, `target_value`, `status`, `calculated_at`.
- **`soc_operational_kris`**: `kri_id` (PK), `kri_name`, `current_value`, `threshold_value`, `status`, `calculated_at`.

### 1.3 Risk Quantification (`cyber_risk_records`)
- **`cyber_risk_records`**: `risk_id` (PK), `risk_fingerprint` (UQ), `scenario_type`, `title`, `description`, `exposure_value`, `single_loss_expectancy`, `annualized_loss_expectancy`, `inherent_risk_score`, `residual_risk_score`, `mitigation_effectiveness`, `status`, `scope_id` (FK), timestamps.
- **`cyber_risk_scenarios`**: Implemented as a JSONB column `scenario_metrics` on the `cyber_risk_records` table to avoid over-normalization.
- **`cyber_risk_forecasts`**: `forecast_id` (PK), `risk_id` (FK), `quarter`, `projected_loss`, `exposure_value`.

### 1.4 GRC Intelligence (`grc_assessments`)
- **`grc_assessments`**: `assessment_id` (PK), `assessment_fingerprint` (UQ), `framework_type`, `name`, `description`, `compliance_score`, `framework_coverage`, `control_coverage`, `evidence_completeness`, `audit_readiness`, `status`, `scope_id` (FK), timestamps.
- **`grc_framework_controls`**: `control_id` (PK), `assessment_id` (FK), `control_name`, `framework_type`, `requirement_id`, `status`.
- **`grc_evidence`**: `evidence_id` (PK), `assessment_id` (FK), `file_name`, `file_hash` (UQ), `uploaded_at`.
- **`grc_gaps`**: `gap_id` (PK), `assessment_id` (FK), `gap_type`, `description`, `remediation_plan`.

### 1.5 Security Knowledge (`security_knowledge_records`)
- **`security_knowledge_records`**: `knowledge_id` (PK), `knowledge_fingerprint` (UQ), `knowledge_type`, `title`, `content` (TEXT), `relevance_score`, `confidence_score`, `status`, `tags` (JSONB array), `scope_id` (FK), timestamps.
- **`security_knowledge_relationships`**: `relationship_id` (PK), `source_id` (UUID), `source_type`, `target_id` (UUID), `target_type`, `relationship_type`, `weight`.
- **`security_knowledge_recommendations`**: `recommendation_id` (PK), `knowledge_id` (FK), `title`, `description`, `rank`.

### 1.6 Threat Intelligence (`threat_intel_iocs`)
- **`threat_intel_iocs`**: `ioc_id` (PK), `ioc_fingerprint` (UQ), `value`, `ioc_type`, `severity`, `status`, `reputation`, `feed_type`, `scope_id` (FK), timestamps.
- **`threat_intel_actors`**: `actor_id` (PK), `name`, `description`, `aliases` (JSONB array), `severity`, `status`.
- **`threat_intel_campaigns`**: `campaign_id` (PK), `name`, `description`, `aliases` (JSONB array), `severity`, `status`.
- **Mapping Tables**: `ioc_actor_mapping`, `ioc_campaign_mapping`, `actor_campaign_mapping`.

### 1.7 Security Intelligence Graph (`sig_nodes`)
- **`sig_nodes`**: `node_id` (PK), `node_fingerprint` (UQ), `node_type`, `entity_id` (UUID - polymorphic), `status`, `scope_id` (FK), timestamps.
- **`sig_edges`**: `edge_id` (PK), `edge_fingerprint` (UQ), `source_id` (FK to `sig_nodes`), `target_id` (FK to `sig_nodes`), `edge_type`, `weight`, `status`, `scope_id` (FK).

### 1.8 Security Decision Intelligence (`security_decisions`)
- **`security_decisions`**: `decision_id` (PK), `decision_fingerprint` (UQ), `decision_type`, `target_entity_id` (UUID), `option_name`, `status`, `tradeoff_matrix` (JSONB), `impact_metrics` (JSONB), `scope_id` (FK), timestamps.

### 1.9 Autonomous Planning (`autonomous_plans`)
- **`autonomous_plans`**: `plan_id` (PK), `plan_fingerprint` (UQ), `category`, `name`, `status`, `priority`, `roadmap` (JSONB), `scope_id` (FK), timestamps.
- **`autonomous_plan_milestones`**: `milestone_id` (PK), `plan_id` (FK), `name`, `milestone_type`, `target_entity_id` (UUID), `status`, `due_date`, `completed_at`.

### 1.10 Unified Security Intelligence Fabric (`fabric_nodes`)
- **`fabric_nodes`**: `node_id` (PK), `node_fingerprint` (UQ), `source_type`, `status`, `priority`, `confidence_weights` (JSONB), `scope_id` (FK), timestamps.
- **`fabric_propagations`**: `propagation_id` (PK), `source_node_id` (FK), `target_node_id` (FK), `mode`, `confidence_score`, `decay_factor`, `timestamp`.
- **`fabric_correlations`**: `correlation_id` (PK), `domain_source`, `domain_target`, `relationship_strength`.

*(All domains will also have an associated `*_history` table containing `id`, `parent_id`, `timestamp`, `event_type`, and `details` JSONB for audit trailing).*

---

## 2. Indexing Strategy

To ensure high performance for complex graph and intelligence queries:
1.  **Scope Filtering**: B-Tree indexes on `scope_id` for all tables.
2.  **Fingerprint Lookups**: Unique constraints on `*_fingerprint` columns.
3.  **Graph Traversal**: Composite indexes on `(source_id, target_id)` for `sig_edges` and `fabric_propagations`.
4.  **Temporal Queries**: BRIN (Block Range Index) or B-Tree indexes on `created_at` and `updated_at` for time-series analysis (e.g., SOC KPIs over time).

---

## 3. Alembic Migration Plan

Due to the massive surface area, rolling this out in a single migration is a bottleneck risk. We will segment the migrations sequentially by domain:

-   `rev_003_grc_and_resilience.py`
-   `rev_004_soc_and_risk.py`
-   `rev_005_knowledge_and_threat.py`
-   `rev_006_graph_and_fabric.py`
-   `rev_007_decision_and_planning.py`

This ensures that schema reviews can be isolated and rollbacks are manageable.

---

## 4. Repository Architecture

We will deprecate the use of `CacheDict` for primary data storage.
1.  **Introduce `SQLAlchemy` Repositories**: Create `src/infrastructure/repositories/` containing domain-specific repository classes (e.g., `GRCRepository`, `ThreatIntelRepository`).
2.  **Async Sessions**: Repositories will accept `AsyncSession` injections.
3.  **Service Refactoring**: Modify the 308 service files to call `await self.repository.get_by_id(...)` instead of accessing the in-memory dicts.

---

## 5. Storage Adapter and Cache Strategy

The `StorageFactory` and `RedisStorageAdapter` will be repurposed exclusively for **caching**, not primary persistence.

1.  **Primary Persistence**: PostgreSQL (via SQLAlchemy).
2.  **L1 Cache (Memory)**: Highly ephemeral, process-local caching for static lookups (e.g., Framework definitions) using `lru_cache`.
3.  **L2 Cache (Redis)**: Distributed caching using `RedisStorageAdapter` for expensive aggregations (e.g., `GraphSnapshotResponse`, `SOCQueueSummary`).
    *   **Write-through Cache**: When a repository updates an entity, it explicitly invalidates the associated Redis keys.
    *   **TTL Strategy**: All cached data will have a strict TTL (e.g., 5-15 minutes) to ensure eventual consistency.

---

## 6. Data Retention Strategy

Intelligence systems generate massive amounts of history and propagation events.
1.  **History Tables**: Implement a Celery beat task (`tasks.purge_intelligence_history`) that runs nightly and deletes rows from all `*_history` and `fabric_propagations` tables where `timestamp < NOW() - INTERVAL '90 days'`.
2.  **Soft Deletes**: Primary entities (Assessments, Plans, Risks) will implement soft deletion (`status = 'ARCHIVED'` or `deleted_at`) rather than hard deletion, ensuring historical graph integrity.
3.  **Graph Edges**: When a node is archived, its associated edges in `sig_edges` will be marked `status = 'DEPRECATED'` rather than deleted.
