# AegisX Sprint 37.6B — Persistence Implementation Plan

**Objective:** Production-grade implementation blueprint to execute the frozen Sprint 37.6A Architecture Decision Record (ADR), eliminating CRIT-06 (In-Memory State Data Loss).
**Author:** Principal Architecture Team
**Constraint:** Implementation Planning Only. No code generation.

---

## SECTION 1 — IMPLEMENTATION PHASE BREAKDOWN

### Phase 1: Foundation (Multi-Tenancy & Event Store)
*   **Objective:** Establish core tenant isolation and central event outbox.
*   **Deliverables:** `tenant_id` injection on core tables, RLS policies, `intelligence_events` partitioned table.
*   **Dependencies:** None.
*   **Complexity:** Medium.
*   **Rollback Risk:** High (Altering core base).
*   **Verification:** Unit tests confirming RLS blocks cross-tenant reads.

### Phase 2: Domain Persistence (Base Intelligence)
*   **Objective:** Migrate isolated domains (GRC, Resilience, Threat, Knowledge, SOC) to PostgreSQL.
*   **Deliverables:** SQLAlchemy models, Repositories, Alembic migrations.
*   **Dependencies:** Phase 1.
*   **Complexity:** High (Volume of models).
*   **Rollback Risk:** Low (New tables).
*   **Verification:** Integration tests verifying CRUD per domain.

### Phase 3: Cross-Domain Persistence (Risk, Planning, Decisions)
*   **Objective:** Migrate complex aggregates that reference base intelligence.
*   **Deliverables:** Repositories, JSONB aggregates (tradeoffs, roadmaps).
*   **Dependencies:** Phase 2.
*   **Complexity:** High.
*   **Rollback Risk:** Low.
*   **Verification:** E2E tests for decision tradeoff calculations saving correctly.

### Phase 4: Graph & Fabric Projections
*   **Objective:** Implement CQRS read models for Graph and Fabric.
*   **Deliverables:** Projection handlers, Materialized Views, `sig_nodes`/`edges`.
*   **Dependencies:** Phase 1, 2, 3.
*   **Complexity:** Critical.
*   **Rollback Risk:** Medium.
*   **Verification:** Graph paths resolve correctly after domain entity creation.

### Phase 5: Service Refactoring & Cache Migration
*   **Objective:** Replace `CacheDict` in the 308 domain services.
*   **Deliverables:** Services wired to `UnitOfWork` and Redis L2 Cache.
*   **Dependencies:** Phase 1-4.
*   **Complexity:** Critical (Refactoring live logic).
*   **Rollback Risk:** High.
*   **Verification:** All endpoints function seamlessly against Postgres.

---

## SECTION 2 — DATABASE IMPLEMENTATION PLAN

**Table Inventory & Ownership:**
1.  **Core:** `tenants` (Core Team).
2.  **Audit:** `intelligence_events` (Platform Team).
3.  **Resilience:** `cyber_resilience_records`, `cyber_resilience_objectives`.
4.  **SOC:** `soc_analytics_records`, `soc_operational_kpis`, `soc_operational_kris`, `soc_analyst_performance`.
5.  **Risk:** `cyber_risk_records`, `cyber_risk_forecasts`.
6.  **GRC:** `grc_assessments`, `grc_framework_controls`, `grc_evidence`, `grc_gaps`.
7.  **Knowledge:** `security_knowledge_records`, `security_knowledge_relationships`, `security_knowledge_recommendations`.
8.  **Threat:** `threat_intel_iocs`, `threat_intel_actors`, `threat_intel_campaigns`, mapping tables.
9.  **Decisions:** `security_decisions` (JSONB tradeoffs/impacts).
10. **Planning:** `autonomous_plans` (JSONB roadmaps), `autonomous_plan_milestones`.
11. **Fabric:** `fabric_nodes` (JSONB weights), `fabric_propagations`, `fabric_correlations`.
12. **Graph (Projections):** `sig_nodes`, `sig_edges`.

**Implementation Strategy:**
*   **Foreign Key Strategy:** Strict referential integrity. Deleting a scope/tenant cascades. Exclusive subtyping for graph nodes (e.g., `asset_id`, `risk_id`).
*   **Tenant Isolation:** `tenant_id` on ALL tables. 
*   **RLS Rollout:** Apply `ALTER TABLE x ENABLE ROW LEVEL SECURITY;` + `CREATE POLICY tenant_isolation ON x USING (tenant_id = current_setting('app.tenant_id')::uuid);`.
*   **Partitioning:** `intelligence_events` and time-series (SOC KPIs, Fabric propagations) partitioned `BY RANGE (timestamp)` monthly.

---

## SECTION 3 — REPOSITORY IMPLEMENTATION PLAN

**Required Repositories:**
*   `GRCRepository` (Assessments, Gaps, Evidence)
*   `RiskRepository` (Risks, Forecasts)
*   `ThreatRepository` (IOCs, Actors, Campaigns)
*   `KnowledgeRepository` (Articles, Relationships)
*   `SOCRepository` (Analytics, KPIs, Analysts)
*   `EventRepository` (Audit logs, Outbox)
*   `GraphRepository` (Read-only projections)
*   `PlanningRepository` (Plans, Milestones)
*   `DecisionRepository` (Decisions, Tradeoffs)
*   `FabricRepository` (Nodes, Propagations)

**Responsibilities:**
Isolate SQLAlchemy syntax from business logic. Domain services only know about domain aggregates (Pydantic models), repositories handle the ORM translation.
**Transaction Boundaries:** Repositories do NOT call `.commit()`.

---

## SECTION 4 — UNIT OF WORK IMPLEMENTATION PLAN

**Design:**
The Unit of Work (UoW) manages the `AsyncSession` lifecycle.
```python
async with UnitOfWork() as uow:
    risk = await uow.risk_repo.get(id)
    risk.update_score()
    await uow.risk_repo.save(risk)
    await uow.event_repo.publish(...)
    await uow.commit() # Atomic save of both table and event log
```
*   **Session Lifecycle:** One per HTTP request/worker task.
*   **Commit Strategy:** Explicit commit at the end of the UoW block.
*   **Rollback Strategy:** Automatic `.rollback()` in `__aexit__` if an exception occurs.

---

## SECTION 5 — EVENT ARCHITECTURE IMPLEMENTATION PLAN

**Transactional Outbox Recommendation: YES.**
To guarantee graph projection consistency, we must implement a **Transactional Outbox Pattern**.

**Design:**
1.  **Publishing Flow:** When a service creates a new Risk, it writes the `cyber_risk_records` row AND a row to `intelligence_events` (status: `PENDING`) inside the *same UoW transaction*.
2.  **Consumption Flow:** A background Celery worker (or Postgres CDC) polls `intelligence_events` for `PENDING` events.
3.  **Projection Update Flow:** The worker executes CQRS projection handlers (e.g., `UpdateGraphNodeHandler`), updating `sig_nodes`, and marks the event `PROCESSED`.

---

## SECTION 6 — GRAPH PROJECTION IMPLEMENTATION PLAN

**Design:**
*   **Projection Generation:** Graph nodes and edges are strictly generated via Event Consumption (Section 5).
*   **Materialized Views:** Create `vw_graph_impact_paths` refreshed concurrently every 5 minutes for the Executive Dashboard.
*   **Future Neo4j Path:** Because the Graph is populated via the Event Outbox, switching to Neo4j merely requires adding a second event consumer that pushes Cypher queries to Neo4j, without touching the core Postgres tables.

---

## SECTION 7 — CACHE IMPLEMENTATION PLAN

**L1 Cache (Memory):**
*   **Allowed:** NIST CSF mappings, severity enum lists, feature flags.
*   **Forbidden:** ANY customer data, `tenant_id` specific data, transient operational state.

**L2 Cache (Redis):**
*   **Cached Read Models:** Executive Dashboard summaries, SOC KPI aggregates, active threat feeds.
*   **TTL Strategy:** 5 minutes for dashboards, 1 hour for threat feed buffers.
*   **Invalidation Strategy:** Time-based expiration (Eventual Consistency).

---

## SECTION 8 — SERVICE REFACTORING PLAN

**Services Requiring Modification:** All 308 files in `src/services/`. Specifically stripping out `CacheDict`.
**Refactoring Sequence:**
1.  Inject `UnitOfWork` into service constructors.
2.  Replace `self._cache.get(id)` with `await uow.repo.get(id)`.
3.  Replace `self._cache[id] = obj` with `await uow.repo.save(obj)` and `await uow.commit()`.
**Risk Areas:** Asynchronous deadlocks if UoW is nested incorrectly. Distributed transaction boundaries.

---

## SECTION 9 — TESTING STRATEGY

*   **Target Coverage:** 90%
*   **Unit Tests:** Business logic mapping functions (Pydantic to SQLAlchemy).
*   **Repository Tests:** Against testcontainers (PostgreSQL). Verifying complex JSONB extraction.
*   **RLS Tests:** Critical. Authenticate as Tenant A, verify 0 rows returned for Tenant B's data.
*   **CQRS/Projection Tests:** Emit a mock event, verify the Materialized View logic correctly updates.
*   **Migration Tests:** Downgrade/Upgrade tests for Alembic.

---

## SECTION 10 — DEPLOYMENT STRATEGY

1.  **Migration Rollout:** Deploy Phase 1-5 schema migrations sequentially using Alembic.
2.  **Background Workers:** Start Outbox processing workers (Celery).
3.  **Application Rollout:** Perform a rolling update of the API pods containing the refactored services.
4.  **Verification Steps:** 
    * Verify no 500 errors on dashboard loads.
    * Run a health check against the RLS policies.
    * Verify Event Outbox backlog is clearing.
5.  **Rollback Plan:** Stop API, run Alembic downgrade, restart old API image.

---

## SECTION 11 — IMPLEMENTATION RISKS

| Risk | Severity | Mitigation Strategy |
| :--- | :--- | :--- |
| **RLS Misconfiguration** | CRITICAL | Dedicated test suite running queries as explicitly mapped test tenants. Code reviews mandate RLS policies on ALL new migrations. |
| **Outbox Processing Lag** | HIGH | Add Prometheus metrics for `outbox_pending_count`. Auto-scale Celery workers if lag > 30s. |
| **UoW Deadlocks** | MEDIUM | Enforce `pylint` rules blocking nested `async with UnitOfWork()` calls in the codebase. |
| **Materialized View Lock Contention** | MEDIUM | Use `REFRESH MATERIALIZED VIEW CONCURRENTLY` to prevent read blocking. |

---

## SECTION 12 — SPRINT EXECUTION PLAN

| Phase | Description | Estimated Effort |
| :--- | :--- | :--- |
| **Phase 1** | Multi-Tenancy Foundation & Event Store | 2 Days |
| **Phase 2** | Base Intelligence Persistence (CRUD domains) | 4 Days |
| **Phase 3** | Cross-Domain Persistence (Complex aggregates) | 3 Days |
| **Phase 4** | Outbox Handlers & Graph Projections | 3 Days |
| **Phase 5** | Service Refactoring (`CacheDict` removal) | 5 Days |
| **Phase 6** | Unit & Integration Testing Validation | 3 Days |
| **Phase 7** | Cache Implementation & Verification | 1 Day |

**Total Estimated Implementation Time:** ~3 Weeks (1 Engineering Squad).
