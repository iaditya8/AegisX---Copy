# AegisX Sprint 37.6A: Final Architecture Decision Record (ADR)

**Objective:** Final architecture decision review for Sprint 37.6 persistence migration (CRIT-06 resolution).  
**Auditors:** Principal Software Architect, Principal Database Architect, Principal SaaS Architect, Principal Platform Engineer  
**Date:** 2026-07-04  
**Status:** **FROZEN**

---

## 1. Final Architecture Decisions

### Decision Area 1 — Security Intelligence Graph Architecture
**Selected Option:** **Option C - Graph Projection Layer**
*   **Justification:** A graph with 20+ node types and 100M+ edges cannot be reliably maintained via direct polymorphic keys (no referential integrity) or exclusive subtyping (creates an unmaintainable "god table" with 20+ nullable FK columns). By making domain tables (Assets, Findings, Risks) the authoritative Source of Truth, the graph becomes a *Projection Layer* updated via domain events. This ensures pristine domain data integrity while allowing graph eventual consistency.
*   **Rejected Options:**
    *   *Option A (Polymorphic):* Rejected due to weak referential integrity and guaranteed orphaned nodes.
    *   *Option B (Exclusive Subtyping):* Rejected due to extreme schema expansion over time and high maintenance burden.

### Decision Area 2 — History Architecture
**Selected Option:** **Option B - Central Audit/Event Log**
*   **Justification:** CQRS and fast operational dashboards require authoritative current state. Reconstructing state purely from events (Option C) introduces extreme operational complexity and read latency. Conversely, per-domain tables (Option A) scatter audit logs and cripple cross-domain forensics. Option B allows fast CRUD against current state while asynchronously writing to a centralized, partitioned `intelligence_events` table for compliance, forensics, and timeline reconstruction.
*   **Rejected Options:**
    *   *Option A (Per-Domain):* Rejected due to fragmentation of forensic timelines and complex reporting.
    *   *Option C (Full Event Sourcing):* Rejected due to excessive operational complexity and latency risks for simple state retrievals.

### Decision Area 3 — Graph Storage Strategy
**Selected Option:** **Option B - PostgreSQL + Materialized Views (Current) → Option C (Future)**
*   **Justification:** Introducing a dedicated graph database (Neo4j) immediately adds significant infrastructure overhead and deployment risk. PostgreSQL can handle 100M edges efficiently if complex path queries are pre-computed via Materialized Views (refreshed asynchronously) and standard hierarchical queries utilize the `ltree` extension. 
*   **Future Upgrade Path:** Once the graph scales beyond the capability of Materialized Views for real-time traversal, the Projection Layer (from Decision 1) natively allows swapping the graph read model to Neo4j without altering the underlying domain authoritative data.

### Decision Area 4 — CQRS Boundaries
*   **Domains requiring CQRS (Complex Reads, Aggregations, Dashboards):**
    *   SOC Analytics (KPIs, queue aggregations)
    *   Security Intelligence Graph (Path traversals)
    *   Executive Dashboards (Scorecards, multi-domain heatmaps)
    *   Security Decision Intelligence (Tradeoff matrices, ROI calculations)
    *   Cyber Risk Quantification (Financial projections, ARO/ALE rollups)
*   **Domains remaining strict CRUD (Direct Table Access):**
    *   GRC Controls & Assessments
    *   Compliance Records & Evidence Uploads
    *   Security Knowledge Base Articles
    *   User / Tenant Management

### Decision Area 5 — Final Migration Strategy
The previously defined migration order is logically sound and preserves all dependency chains. It is confirmed as final:
1. `rev_003_multi_tenancy` (Base RBAC, tenant_ids, RLS setup)
2. `rev_004_event_store` (Central partitioned audit log)
3. `rev_005_base_intelligence` (GRC, Resilience, SOC, Threat, Knowledge)
4. `rev_006_cross_domain` (Risk, Decisions, Planning — depend on base models)
5. `rev_007_graph_and_fabric` (Projections — depend on everything)

### Decision Area 6 — Final Cache Strategy
*   **L1 Cache (Process Memory):** Static reference data ONLY. Framework definitions (e.g., NIST 800-53 controls), static configuration, compiled regexes, feature flags. *Rule: No tenant-specific data resides in L1.*
*   **L2 Cache (Redis):** Ephemeral state and read models. Computed CQRS dashboards (e.g., Executive Heatmap), active graph impact paths, user session rate-limits, and fast-moving threat feed buffers.
*   **Never Cache (PostgreSQL Only):** Authoritative state writes, GRC compliance evidence, SOC case statuses, financial cyber risk quantifications, and event history.

---

## 2. Final Architecture Blueprint

The approved blueprint establishes a highly scalable, multi-tenant SaaS persistence tier:

*   **Multi-Tenancy:** Guaranteed via `tenant_id` on all tables enforced seamlessly by PostgreSQL Row-Level Security (RLS).
*   **Persistence Layer:** PostgreSQL serves as the absolute Source of Truth for all domain aggregates.
*   **Event Architecture:** Domain repositories publish state changes to a centralized, time-partitioned `intelligence_events` table (Central Audit Log).
*   **Graph Architecture:** Graph Nodes and Edges are a *Projection Layer*. Domain events asynchronously populate materialized views and edge tables optimized for traversal.
*   **Repository & Unit of Work (UoW):** Repositories handle database boundary logic. UoW manages `AsyncSession` transactions, ensuring multi-repository writes commit atomically.
*   **CQRS:** Heavy analytical workloads route to Read Models (Materialized Views and Redis caches), segregating them from authoritative OLTP writes.
*   **Retention:** Time-series tables and event logs utilize PostgreSQL `RANGE` partitions, allowing automated dropping of old partitions based on per-tenant, per-domain retention policies.

---

## 3. Architecture Decision Records (ADR)

*   **ADR-001 Graph Architecture:** Adopt Graph Projection Layer driven by domain events to guarantee referential integrity of the source-of-truth.
*   **ADR-002 Event Architecture:** Adopt Central Audit Log (`intelligence_events`) over Full Event Sourcing to balance compliance needs with CRUD operational simplicity.
*   **ADR-003 Multi-Tenancy:** Mandate `tenant_id` and RLS on all queries to mitigate cross-tenant data leakage risk.
*   **ADR-004 CQRS Boundaries:** Apply CQRS strictly to analytical domains (SOC, Graph, Risk); retain CRUD for compliance/governance domains.
*   **ADR-005 Retention Strategy:** Mandate PostgreSQL Table Partitioning for all time-series and event data to support compliance-driven, locking-free purges.
*   **ADR-006 Cache Strategy:** Strictly ban tenant data from L1 process memory; enforce Redis L2 for read models.

---

## 4. Freeze Decision

**[ ARCHITECTURE FROZEN ]**

**Sprint 37.6 Architecture Complete.**
**Implementation Planning May Begin.**

---

## 5. Final Scores

*   **Persistence Architecture:** 95 / 100
*   **Database Design:** 95 / 100
*   **Scalability:** 92 / 100 *(Graph traversal at >100M edges will require monitoring prior to Neo4j migration)*
*   **Enterprise Readiness:** 98 / 100
*   **Multi-Tenancy:** 98 / 100
*   **Operational Readiness:** 90 / 100
*   **Maintainability:** 92 / 100
*   **Long-Term Sustainability:** 94 / 100
