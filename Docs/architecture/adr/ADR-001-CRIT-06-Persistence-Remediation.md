# Architecture Decision Record: ADR-001-CRIT-06-Persistence-Remediation

* **Status**: Accepted
* **Date**: 2026-07-05
* **Deciders**: 
  - Principal Software Architect
  - Principal Database Architect
  - Principal Security Architect

---

## 1. Original Finding (Context)

During the Sprint 37.6 compliance audit under **CRIT-06**, a critical vulnerability was identified across multiple core domains: the platform relied on transient, class-level in-memory dictionaries (`dict`, singletons, global stores) as the authoritative source of truth.

### Key Risks Identified:
1. **Lack of Durability**: Application restarts or container crashes resulted in complete data loss of security configurations, incident records, and history trails.
2. **RLS Bypass**: Multi-tenant isolation enforced via PostgreSQL Row-Level Security (RLS) was bypassed for in-memory operations, creating security boundary risks.
3. **No Auditability**: Operations on transient objects did not leave persistent database logs or outbox events for downstream synchronization.

---

## 2. Affected Domains

The audit classified 11 critical domains under compliance risk:
1. **Threat Intelligence Domain** (IOCs, Actors, Campaigns)
2. **Security Intelligence Graph Domain** (Nodes, Edges)
3. **Incident Management & Investigation**
4. **Risk Acceptance**
5. **Remediation & SLA**
6. **Threat Hunting & IOC Scan**
7. **Unified Security Intelligence Fabric**
8. **Security Posture**
9. **Security Decision**
10. **Security Program**
11. **Purple Team Emulation**

---

## 3. Remediation Phases

The remediation was executed in three distinct iterations to guarantee zero platform regression.

### Sprint 37.6B Phase 1
- **Focus**: Core Threat Intelligence & Security Intelligence Graph.
- **Actions**:
  - Replaced transient stores with repositories (`ThreatRepository`, `GraphRepository`) mapped to PostgreSQL.
  - Reconfigured `CacheDict` adapters to act strictly as L2 caches.
  - Routed all writes through the `UnitOfWork` manager to ensure transaction consistency.

### Sprint 37.6B Phase 2
- **Focus**: Multi-Tenancy Boundary Isolation & Outbox.
- **Actions**:
  - Enforced Row-Level Security (RLS) at the database layer using Alembic migrations.
  - Integrated `IntelligenceEvent` outbox structures to stage notifications within the same db transaction.
  - Implemented `GraphBootstrapService` to warm the graph L2 cache on application start.

### Sprint 37.6C
- **Focus**: Final 9 Compliance Gaps Remediation.
- **Actions**:
  - Migrated Incident, Risk, Remediation, Hunt, Fabric, Posture, Decision, Program, and Purple Team domains.
  - Added dedicated repositories, async endpoints, and bootstrap sequences for each domain.
  - Fully integrated all 9 domains into the cold-start cache warming sequence (`CacheBootstrapService`).

---

## 4. Final Closure Audit

On 2026-07-05, a final closure audit was performed:
- **Scope**: Actual codebase, including all services, repositories, and caches.
- **Result**: 100% of integration test cases (410 tests) successfully executed and passed.
- **Verdict**: **CRIT-06 CLOSED**

---

## 5. Lessons Learned

1. **Authoritative State Isolation**: Application service classes must remain stateless. All state modifications must be persisted down to the database before returning control to the caller.
2. **Unified Transaction Lifecycle**: The `UnitOfWork` pattern must wrap all service operations. Staging and committing database entities and outbox events together guarantees consistency.
3. **Multi-Tenant RLS Boundaries**: Database RLS settings must be strictly mapped. Passing tenant settings correctly via context propagates boundaries reliably.

---

## 6. Future Requirements

Future contributors and agents must adhere to the following rules:
- **No transient variables** (e.g., `_incidents`, `_hunts`) may serve as the authoritative state.
- Every new domain model must inherit from `TenantOwnedMixin` and `AuditMixin`.
- Outbox events must be staged using `uow.session.add(event)` before committing.
- Any cache adapter must have a cold-start `bootstrap(cls, db: AsyncSession)` registration in `CacheBootstrapService`.
