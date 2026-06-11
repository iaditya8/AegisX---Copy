# Roadmap — AegisX (Milestone-driven)

This roadmap is prepared by the CTO / Principal Architect / Product Manager. It organizes work into milestone-driven phases (no dates) and aligns roadmap goals with Attack Surface Management, Asset Discovery, Vulnerability Assessment, Risk Correlation, and Reporting.

Phases:

- Phase 0: Foundation
- Phase 1: MVP
- Phase 2: Asset Intelligence
- Phase 3: AI Security Copilot
- Phase 4: Enterprise Features
- Phase 5: SaaS Platform

Each phase is expressed as a set of milestones (Mx.y). For each milestone we list Objectives, Features, Deliverables, Dependencies, and Success Criteria. Milestones are grouped into Technical, Product, and Infrastructure categories where relevant.

---

## Cross-cutting (applies to all phases)

- Security Hardening Program: threat modeling, SAST, dependency scanning (SCA), secrets detection, container scanning, RBAC review, DAST/pentest cycle. Every release gate must show no Critical vulnerabilities.
- Observability & SLOs: structured logs, metrics, tracing, health checks, and dashboarding.
- CI/CD & Migrations: automated tests, migration tooling (Alembic), image signing and reproducible builds.
- Plugin Contract & Sandbox: define plugin API, capability manifest, and execution sandbox for scanner integrations.

### Architecture Decision Records (ADR)

Purpose: record important architecture decisions, their rationale, alternatives, and consequences to provide institutional memory and enable clear review and rollback paths.

When ADRs are required:
- Database changes (schema or major model changes)
- Authentication or authorization model changes
- Infrastructure topology or deployment model changes
- Major technology replacements (e.g., introducing a new DB or queue)
- AI/ML architecture changes (model hosting, data retention, RAG design)

Required ADR structure:
- Context: background, constraints and forces.
- Decision: the chosen approach and summary of the decision.
- Alternatives Considered: other viable options and trade-offs.
- Consequences: operational impact, migration steps, and known risks.

Policy: ADRs must be authored for the items above, stored under `docs/adr/` with a link included in the related milestone acceptance checklist.

---

## Phase 0 — Foundation

Objective: establish developer ergonomics, baseline security, and core infra to enable reliable product development.

Technical milestones (M0.x):
- M0.1: Repo & CI hygiene — repo structure, linters, unit tests, GitHub Actions CI with SAST and SCA in pipeline.
- M0.2: Local dev stack — Docker Compose with Postgres, Redis, object storage emulator, documented dev runbook.
- M0.3: Initial DB & API contracts — implement baseline schema, OpenAPI stub, and migration skeleton.

Product milestones:
- M0.P1: Finalize and approve PRD, Vision, and MVP feature list.
- M0.P2: Draft UX flows for scope onboarding and reporting.

Infrastructure milestones:
- M0.I1: Artifact registry and image build pipeline.
- M0.I2: Secrets handling policy (env vs vault) for development and CI.

Deliverables:
- Working local environment, CI pipelines with SCA/SAST, baseline DB migrations, OpenAPI spec skeleton, contributor docs.

Dependencies: core tech choices (Python/FastAPI/Postgres), container tooling, scanner binaries licensing.

Success Criteria:
- Full-stack runs locally in <15 minutes; CI passes on PRs; security gates configured in CI.

## Phase 0.5 — Architecture Freeze

Objective: Freeze v1 documentation and designs before implementation begins.

Technical milestones (M0.5.x):
- M0.5.1: Approve `Docs/03_Architecture.md` (architecture) via ADR and sign-off.
- M0.5.2: Approve `Docs/04_Database.md` (database) and migration plan.
- M0.5.3: Approve `Docs/05_API.md` (API) and OpenAPI contract.
- M0.5.4: Approve `Docs/CodingStandards.md` (coding standards and linting rules).
- M0.5.5: Approve `Docs/AgentRules.md` (agent/plugin rules and sandboxing requirements).

Product milestones:
- M0.5.P1: Freeze MVP scope and acceptance criteria; capture any outstanding change requests as backlog items.

Infrastructure milestones:
- M0.5.I1: Verify CI/CD gating, artifact promotion, and infra runbooks for v1 deployment.
- M0.5.I2: Ensure secrets management and image signing policies are in place for production images.

Deliverables:
- Approved PRD, Vision, Architecture, Database, API, Coding Standards, Agent Rules; documentation tagged `v1.0`.

Success Criteria:
- Documentation version `v1.0` is tagged in the repo.
- Architecture/Database/API/CodingStandards/AgentRules have explicit approvals recorded (PR approvals + ADRs where applicable).
- No implementation work starts for v1 features until approvals are complete.

---

## Phase 1 — MVP

Objective: deliver the core product offering: scope management, discovery, scanning with Nuclei, asset inventory, and basic reporting.

Technical milestones (M1.x):
- M1.1: Scope Management API + UI — CRUD for scopes, validation and policy enforcement.
- M1.2: Recon Engine v1 — orchestrate Subfinder, Amass, dnsx; normalise outputs to `assets` table.
- M1.3: Scan Orchestration v1 — integrate Naabu, httpx; implement plugin runner and sandbox basics.
- M1.4: Vulnerability Integration — run Nuclei templates and persist `findings` with fingerprints.
- M1.5: Reporting & Exports — Markdown/HTML report generator and artifact storage.

Product milestones:
- M1.P1: End-to-end user flow: create scope → run discovery → view assets → run scans → generate report.
- M1.P2: Basic RBAC: roles (admin, operator, reader), session management, audit trail for actions.

Infrastructure milestones:
- M1.I1: Staging deployment (single-region), backups, restore drill for Postgres & object store.
- M1.I2: Queue & workers (Redis/Celery) with retry and dead-letter handling.

Deliverables:
- Release candidate container images, documentation for scan ops, initial runbook, sample Nuclei template pack.

Dependencies: Phase 0 completion, scanner binaries and runtime licenses, object store.

Success Criteria:
- Demonstrable E2E scans and report generation on staging; zero Critical security findings; core SLOs for asset discovery and report generation met.

MVP Features (must ship in Phase 1):
- Scope Management, Recon Engine (Subfinder/Amass/dnsx), Asset Inventory, Naabu/httpx scanning, Nuclei integration, PostgreSQL persistence, FastAPI endpoints, Markdown/HTML reporting.

---

## Phase 2 — Asset Intelligence

Objective: add richer context, time-series history, and relationship modeling to improve prioritization and triage.

Technical milestones (M2.x):
- M2.1: Asset History & Lineage — store state changes with time-series-friendly schema and retention policies.
 - M2.2: Graph Model Prototype (PostgreSQL-first) — implement relationship intelligence using PostgreSQL (recursive CTEs, JSONB, GIN/trgm patterns) and build a proof-of-concept for relationship traversal and performance. Neo4j is optional and deferred; adoption requires proven performance bottlenecks, explicit enterprise graph requirements, an architecture review approval, and a cost-benefit analysis.
- M2.3: Enrichment Pipeline — WHOIS, ASN, Passive DNS, CT, certificate parsing.
- M2.4: Correlation Engine v1 — combine signals across runs to dedupe and surface persistent vs transient findings.

Product milestones:
- M2.P1: Asset activity timelines in UI; filters by first/last seen and persistence score.
- M2.P2: Prioritization ruleset editor for security teams.

Infrastructure milestones:
 - M2.I1: Storage strategy for large artifact volumes (partitioning & lifecycle to object storage).
 - M2.I2: Graph evaluation and benchmarking tooling — benchmark PostgreSQL relationship approaches; provision Neo4j only if PostgreSQL proves insufficient and after architecture review and cost-benefit approval.

Deliverables:
- Enrichment connectors, graph POC (PostgreSQL-first; Neo4j deferred), updated API for historical queries, migration scripts and backfills.

Dependencies: stable MVP schema, external enrichment providers and rate limits.

Success Criteria:
- Correlation reduces noise/false positives and enables faster triage (measurable reduction in mean time to acknowledge).

Post-MVP Features (Phase 2):
- Asset lineage, enrichment stack, graph relationships, advanced deduplication and historical queries.

---

## Phase 3 — AI Security Copilot

Objective: introduce AI-assisted triage, natural-language assistance, and automated risk scoring to accelerate operations.

Technical milestones (M3.x):
- M3.1: Feature Store & Scoring Pipeline — prepare data for model consumption and realtime scoring.
- M3.2: Secure LLM Proxy & RAG — implement retrieval-augmented generation with strict context limits and auditable prompts.
- M3.3: Copilot Workflows — natural-language queries, auto-generated executive summaries, remediation suggestions with confidence scores.
- M3.4: Audit & Governance — logging of AI decisions, manual approval steps and rollback controls.

Product milestones:
- M3.P1: Operator Copilot in UI (query box + suggested actions).  
- M3.P2: Executive summary generation for scheduled reports.

Infrastructure milestones:
- M3.I1: Model hosting or secure cloud LLM integration; cost monitoring and rate limiting.
- M3.I2: Feature store and ML infra for offline evaluation.

Deliverables:
- Copilot UI, evaluation reports, drift detection, templates for prompts and human-in-loop flows.

Dependencies: Phase 2 data quality, legal/privacy review, secure model access.

Success Criteria:
- A/B tests demonstrate reduced triage time and improved remediation suggestions precision; auditability of AI actions.

Future Research Features (Phase 3+):
- Predictive risk scoring, automated remediation playbooks, continuous red-team simulation.

---

## Phase 4 — Enterprise Features

Objective: harden product for enterprise adoption: multi-tenancy, SSO/SCIM, compliance, integrations, and scale.

Technical milestones (M4.x):
- M4.1: Multi-tenant data partitioning and isolation model.
- M4.2: SSO/SCIM integration and provisioning flows.
- M4.3: Fine-grained RBAC and policy enforcement engine.
- M4.4: HA & scaling: read replicas, queue clustering, autoscaling workers.

Product milestones:
- M4.P1: SIEM and ticketing connectors (push findings to Splunk/ELK/Jira/ServiceNow).
- M4.P2: Compliance exports and retention controls for auditability.

Infrastructure milestones:
- M4.I1: Production-grade backups, DR runbooks, and canary deploys.
- M4.I2: Observability at scale (Prometheus/Grafana dashboards and alerting policies).

Deliverables:
- Enterprise deployment guides, SSO/SCIM integration docs, capacity planning and SLAs.

Dependencies: validated security posture, scalability testing, enterprise legal requirements.

Success Criteria:
- Platform passes enterprise security review, pilot deployment with customer, meets SLA targets under load.

Enterprise Features (Phase 4):
- Tenant isolation, SSO/SCIM, advanced RBAC, SIEM connectors, audit/export tooling.

---

## Phase 5 — SaaS Platform

Objective: operate AegisX as a managed SaaS with metering, billing, self-serve onboarding and multi-region resilience.

Technical milestones (M5.x):
- M5.1: Metering and billing events pipeline; usage aggregation and billing reconciliation.
- M5.2: Self-serve onboarding + tenant lifecycle automation.
- M5.3: Multi-region object storage and DB replication for global resilience.

Product milestones:
- M5.P1: Trial and conversion funnel with usage dashboards.  
- M5.P2: Marketplace and partner integrations.

Infrastructure milestones:
- M5.I1: Global infra automation (IaC) with multi-region failover tests.
- M5.I2: Billing compliance and support tooling.

Deliverables:
- Pricing model, billing connector, self-serve UX, runbooks for global ops.

Dependencies: enterprise features complete, reliable automation and compliance readiness.

Success Criteria:
- Customers can self-onboard and be billed correctly; multi-region failover validated; billing accuracy verified.

---

## Development sequence & parallelism

- Sequence: Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5.  
- Within phases, prioritize technical milestones that unblock product work (e.g., plugin contract before large-scale scanner integration).  
- Parallel work: frontend UI, integration adapters, and enrichment connectors can proceed in parallel with mocked APIs while core API and workflows are stabilized.

## Team responsibilities (summary)

- CTO/Product: roadmap prioritization, stakeholder alignment, customer pilots.  
- Principal Architect: architecture decisions, plugin API, scalability and security guidance.  
- Backend Eng: API, workflow engine, DB schema/migrations, worker orchestration.  
- Recon/Integrations: scanner plugins, normalization, enrichment connectors.  
- Data/ML: correlation engine, feature store, Copilot models.  
- SRE/Platform: CI/CD, infra automation, backups, monitoring, HA.  
- Frontend: dashboards, UX for workflows and Copilot.

## Risk assessment & mitigations

- Scanner integration complexity: isolate via plugin contracts; incremental adapter work; comprehensive normalization tests.
- Data growth and cost: partitioning, TTLs, archival to object store, cost monitoring.  
- Security exposure from running third-party tools: strict sandboxing, least privilege, egress control, continuous scanning of worker environments.  
- LLM risk (hallucination/privacy): RAG from trusted data, human-in-loop gating, audit trail of AI suggestions.  
- Operational complexity for enterprise/SaaS: invest in automation, runbooks, and pilot programs.

## Phase Exit Criteria

A phase is considered complete only when all of the following are satisfied for that phase and its milestones:

- All milestones and sub-milestones are completed.
- Documentation is updated and reviewed (architecture, API, DB, runbooks).
- Automated and integration tests pass in CI and on staging.
- Security review passes (SAST/SCA/DAST results meet policy; no Critical vulnerabilities outstanding).
- Deployment validation passes (smoke tests, backup/restore drills as applicable).
- Product acceptance criteria are satisfied and sign-off obtained from Product/PM or stakeholders.

The next phase MUST NOT begin until these exit criteria are met and recorded.

## Milestone acceptance template (apply per-Mx.y)

- Functional demo: end-to-end scenario executed with representative data.  
- Non-functional checks: performance, reliability (basic SLOs).  
- Security checks: SAST/SCA/DAST passing policy gates (no Critical findings).  
- Docs & runbooks: operator and user-facing docs published.

---

## Feature classification (quick reference)

- MVP Features: Scope Management; Recon Engine (Subfinder/Amass/dnsx); Asset Inventory; Naabu/httpx scans; Nuclei integration; PostgreSQL store; FastAPI endpoints; basic reporting.
- Post-MVP Features: Enrichment pipeline; Asset history and graph; correlation engine; Copilot prototypes.
- Enterprise Features: Multi-tenancy; SSO/SCIM; fine-grained RBAC; SIEM/ticketing connectors; audit/export tooling.
- Future Research Features: LLM-driven remediation, predictive risk scoring, continuous adversary simulation.

---

Prepared by the CTO / Principal Architect / Product Manager for AegisX.
