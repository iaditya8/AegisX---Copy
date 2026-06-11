# Architecture

This document captures the principal architecture for AegisX based on the Product Requirements (Docs/01_PRD.md), Vision (Docs/02_Vision.md), and MVP scope (Docs/10_MVP.md). It is written from the perspective of the Principal Architect and focuses on high-level structure, boundaries, data flow, plugin model, workflow engine, and deployment patterns.

## Architectural Principles

1. **PostgreSQL First**: Use PostgreSQL for persistent state and structured data until scale dictates otherwise.
2. **Event-Driven Design**: Services communicate asynchronously through well-defined events, promoting loose coupling.
3. **Plugin-First Architecture**: Extensibility is built-in; scanners, enrichers, and parsers are sandboxed plugins.
4. **API-First Development**: All capabilities are exposed via documented APIs before building UI components.
5. **Security First**: Implement least privilege, strong isolation, and secure defaults at every layer.
6. **AI as a Consumer, Not a Core Dependency**: AI enhances data and workflow but the core platform functions without it.
7. **Cloud-Agnostic Deployment**: Avoid vendor lock-in; deployable on any standard container orchestration or VM environment.
8. **Backward-Compatible APIs**: Ensure smooth upgrades and stable integrations for external consumers.
9. **Documentation-Driven Development**: Architecture, APIs, and decisions are documented prior to or alongside implementation.
10. **Simplicity Before Scale**: Build for the MVP with straightforward tools (e.g., Celery, Redis) and evolve only when bottlenecks occur.

## Goals and constraints

- Modular, open architecture (per Vision).  
- Start with an MVP technology stack: FastAPI, PostgreSQL, minimal dashboard, CLI-driven Recon Engine.  
- Security-first: least privilege, auditability, and sandboxing for untrusted plugins.  
- Incremental rollout: support single-host deployment for MVP, design for horizontal scale later.

**Assumptions**: initial deployment is single-tenant, deployed on VMs or a simple container host (Kubernetes excluded from MVP per Docs/10_MVP.md). Event-driven patterns are preferred for loose coupling.

**Audience**: product, platform, backend, and SRE engineers.

**Contents**
- Architectural Principles
- System Architecture
- Service Boundaries
- Data Flow
- Plugin Architecture
- Workflow Engine Design
- Asset Intelligence Layer
- Correlation Service
- Canonical Event Model
- Deployment Architecture

## System Architecture

High level components:

- API & Web Layer: FastAPI-based HTTP API and dashboard host. Handles authentication, request validation, and UI assets. Acts as primary ingress for users and integrations.
- API Gateway / Reverse Proxy: Lightweight reverse proxy (Nginx/Caddy) in front of FastAPI for TLS termination, basic rate limiting and routing.
- Authentication & Authorization: Token-based auth (JWT for MVP) with RBAC assertions for actions (scan start, view reports, manage scope).
- Recon Engine: Worker processes that orchestrate third-party tools (subfinder, amass, naabu, httpx, nuclei). Designed as orchestrated jobs producing normalized events.
- Workflow Engine: Durable task coordinator that manages long-running recon workflows, retries, timers, and state transitions.
- Plugin Host: Extensible plugin subsystem for integrating scanners, parsers, enrichers, and exporters.
- Orchestration & Queue: Lightweight message bus (Redis) and task orchestration (Celery) for dispatching tasks, events, and notifications between components. Keep the architecture simple for MVP. Alternative queue technologies may be evaluated in future ADRs.
- Data Storage:
  - Primary relational store: PostgreSQL (assets, findings, metadata, user records).
  - Object store (optional): for archived report bundles and large artifacts (S3-compatible or local filesystem).
  - Short-lived store/cache: Redis for locks, rate-limiting, and ephemeral state.
- Observability: Centralized logging (structured logs), metrics (Prometheus), and tracing (OpenTelemetry) for visibility.

Design notes:

- Keep the API and Recon Engine decoupled with the queue to allow independent scaling.  
- Recon workers should be process-isolated and executed with constrained privileges.  
- The Workflow Engine must provide durable state and be resilient to restarts.

## Service Boundaries

Define responsibilities and clear contracts to minimize coupling.

- API & Web Layer
  - Responsibilities: HTTP surface, authentication, serving dashboard, request validation, initiating workflows, and presenting aggregated results.
  - Contracts: REST/JSON API, well-documented OpenAPI specification, idempotent endpoints for workflow actions.

- Recon Engine (Workers)
  - Responsibilities: run scanner tools (via subprocess or container), normalize tool outputs into canonical models, emit events to the bus, write intermediate results to storage.
  - Contracts: consume job messages, produce status events and artifacts, adhere to a defined scanner plugin interface.

- Workflow Engine
  - Responsibilities: orchestrate job sequences (discovery → scanning → analysis → reporting), maintain workflow state machine, schedule retries and timeouts.
  - Contracts: exposes an API for starting, pausing, resuming workflows, and emits lifecycle events.

- Plugin Host
  - Responsibilities: load/unload plugins, enforce sandbox, validate plugin manifests, provide plugin lifecycle hooks.
  - Contracts: plugin API surface (register scanners, parsers, enrichers), versioning policy, capability declarations.

- Data Storage
  - Responsibilities: durable storage of assets, findings, and audit logs. Provide transactional guarantees for critical updates.
  - Contracts: schema and migration policy; read/write API surface for internal services only.

- Orchestration/Queue
  - Responsibilities: reliable delivery, retries, and ordering guarantees (best-effort for MVP). Standardize task orchestration around Celery workers.
  - Contracts: message formats (job, event, ack), visibility timeouts, dead-letter handling.

Security boundary summary:

- Plugin Host and Recon Engine are untrusted relative to core API. Network and filesystem isolation required. Plugins must run in constrained environments and must not be permitted to modify core persistent stores directly.

## Correlation Service

Responsibilities:
* Finding Deduplication
* Historical Correlation
* Risk Scoring
* Exposure Analysis
* Severity Adjustment

Inputs:
* Findings
* Assets
* Scan Runs
* Historical Records

Outputs:
* Risk Scores
* Prioritized Findings
* Correlated Events

This service must remain independent from the AI layer. The AI layer should consume correlation outputs instead of raw scanner results.

## Asset Intelligence Layer

Responsibilities:
* Asset Correlation
* Relationship Building
* Historical Tracking
* Exposure Aggregation
* Asset Context Enrichment

Inputs:
* Assets
* Scan Results
* Findings
* Historical Data

Outputs:
* Asset Relationships
* Asset Risk Context
* Asset Timeline
* Prioritized Assets

This layer becomes the foundation of future Asset Intelligence and Attack Surface Management features.

## Canonical Event Model

Purpose:
Standardize communication between:
* Workflow Engine
* Recon Workers
* Plugin Host
* Correlation Service
* Asset Intelligence Layer

Example event types:
* `asset.discovered`
* `asset.updated`
* `scan.started`
* `scan.completed`
* `finding.created`
* `finding.updated`
* `report.generated`
* `workflow.completed`

Sample JSON event structure:
```json
{
  "event_id": "evt_123456789",
  "event_type": "finding.created",
  "timestamp": "2026-06-11T20:00:00Z",
  "version": "1.0",
  "source": "recon-worker-01",
  "payload": {
    "finding_id": "fnd_987654321",
    "asset_id": "ast_11223344",
    "severity": "high",
    "title": "Exposed Admin Panel"
  }
}
```

Explanation:
* **Event versioning**: All events must include a version field to allow backwards-compatible schema evolution.
* **Event validation**: Producers and consumers must validate event payloads against a canonical JSON schema.
* **Event compatibility requirements**: Schema changes must be additive. Breaking changes require a new event type or major version bump. All services must use the canonical event model.

Event Requirements:
- Every event must have a globally unique event_id.
- Every event must include correlation_id for workflow tracing.
- Every event must include source service identifier.
- Events are immutable after publication.
- Consumers must be idempotent.

## Data Flow

End-to-end typical scenario: user registers a domain scope → starts a discovery workflow → assets discovered → vulnerability scans run → results normalized and reported.

1. User initiates workflow via API (POST /workflows). API validates and persists workflow definition in PostgreSQL and enqueues a workflow-start event.
2. Workflow Engine dequeues workflow-start, creates job chain (discovery job → scanning jobs → analysis job → report job), persists job state, and enqueues the first job.
3. Recon Worker pulls the discovery job from the queue, runs configured discovery tools, produces normalized asset events (JSON), and stores raw artifacts in object store.
4. Recon Worker emits asset events to the bus; Workflow Engine transitions job state to completed and enqueues subsequent scan jobs.
5. Scanner workers execute vulnerability scanners (nuclei), normalize findings into canonical findings, persist to PostgreSQL, and emit notifications for critical findings.
6. Analysis/Correlation component consumes findings, correlates with historical data and risk models, and flags prioritized items.
7. Report generator composes Markdown/HTML/PDF bundles from persisted findings and artifacts, stores them in object store, and updates workflow/report status.
8. API surfaces results; users download or request exports.

Reliability considerations:

- Events are idempotent: workers deduplicate using stable keys (asset fingerprint, scan-run id).  
- State transitions are transactional: Workflow Engine persists state before emitting the next job.  
- Dead-letter queue: failures route to a DLQ for manual inspection and retry.

Data model summary (high level):

- Asset (id, scope_id, host, ip, metadata, first_seen, last_seen)  
- ScanRun (id, job_id, type, status, start_ts, end_ts)  
- Finding (id, asset_id, severity, scanner, fingerprint, details, evidence)  
- Workflow (id, owner, definition, state)

## Plugin Architecture

Goals: enable third-party integrations of scanner tools, enrichers, exporters, and custom parsers while maintaining security and stability.

Plugin types:
- Scanner plugins: wrap third-party tools, handle invocation, and normalize outputs.
- Parser plugins: transform raw tool output to canonical findings.
- Enricher plugins: augment findings with external data (WHOIS, ASN, CVE lookups).
- Exporter plugins: push findings to external systems (SIEM, issue trackers).

Plugin model:

- Manifest-driven: each plugin ships with a manifest (name, version, capabilities, entry points, permissions required).
- Registration: plugins are registered via an administrative API and stored in PostgreSQL along with capability declarations.
- Sandboxed execution: plugins run in isolated processes/containers with limited filesystem and network access. For MVP, use process isolation with seccomp/namespace-like limitations where available; plan to migrate to container-based sandboxing for production.
- Interface contract: plugins implement simple JSON-based stdin/stdout RPC or a defined gRPC contract. The host provides helper SDKs for common languages.
- Lifecycle hooks: install, validate, run, health-check, uninstall. The host enforces resource/time quotas and terminates plugins exceeding limits.
- Versioning and compatibility: plugin manifests declare supported host version range; host enforces compatibility rules.

Security controls for plugins:

- Minimal privileges and ACLs for secrets; plugins never receive raw DB credentials.  
- Network egress restrictions by default; explicit allowances granted per-plugin.  
- Execution timeouts, output size limits, and content scanning to prevent exfiltration.

### Plugin Lifecycle States

Plugin states:

* Draft
* Approved
* Disabled
* Deprecated

Rules:

* Only Approved plugins may execute.
* Deprecated plugins cannot be newly installed.
* Disabled plugins cannot execute.
* Plugins must pass validation before approval.

### Plugin Approval Process

Requirements:

* Security review
* Capability review
* Permission review
* Resource limit review

The Plugin Host must enforce plugin state and approval status.

## Workflow Engine Design

Purpose: coordinate multi-stage reconnaissance and scanning workflows, maintain durable state, and provide visibility for long-running operations.

Core properties:

- Durable state: workflow definitions, job state, retries, and history persisted in PostgreSQL.  
- Deterministic state machine: explicit states (pending, running, failed, paused, completed) and transitions.
- Event-driven execution: engine consumes and emits events to the message bus for worker coordination.
- Idempotency: all jobs designed to be idempotent or guarded by dedup keys.

Architecture options (MVP choice and future):

- MVP: PostgreSQL + Celery as the primary architecture for MVP and early growth stages. Implement a lightweight orchestrator within the API process (or a dedicated process) that persists state to PostgreSQL and uses Redis/Celery for job dispatch. This minimizes dependencies and is simpler to operate.
- Future Workflow Evaluation Criteria: Temporal (or equivalent workflow platforms) should only be evaluated if:
  * Workflow volume exceeds 100,000 executions per day.
  * Multi-region workflow execution becomes necessary.
  * Workflow state complexity becomes an operational bottleneck.
  * PostgreSQL + Celery architecture becomes difficult to maintain.

Key capabilities:

- Job composition: create pipelines (discovery → reconnaissance → scanning → analysis → reporting).
- Retry policies: configurable per-job (exponential backoff, max attempts).  
- Timer events: schedule delayed jobs (e.g., re-scan after N days).  
- Human-in-the-loop: support manual approval steps (pause/resume) and escalation.
- Observability: emit lifecycle events for tracing and metrics.

Operational considerations:

- Migrations: ensure workflow state migrations are reversible and covered by automated tests.  
- Scalability: allow the engine to be run as multiple instances with leader-election for cron-like scheduling tasks.

## Deployment Architecture

Design for MVP and future scaling.

Environments:

- Local / Dev: single-host development image using Docker Compose (Postgres, Redis, queue, API, workers).  
- Staging: duplicate of production with realistic data volumes and monitoring.  
- Production: hardened hosts, managed DB, and object storage. For MVP, single-region deployment on VM(s) or ECS-like container host is acceptable.

Topology (MVP):

- Single-host container deployment or small set of VMs: reverse-proxy, FastAPI app, worker processes, PostgreSQL, Redis, and object store (local S3 or managed). Use process isolation for workers and plugin execution.

Scaling plan:

- Vertical first: scale by increasing resources for the API and Postgres for earliest adopters.  
- Horizontal for workers: add additional Recon Worker instances consuming from the queue.  
- Sharding: partition long-term telemetry and assets by customer (future multi-tenant design).

Security and operations:

- Secrets management: use vault or environment-based secrets for MVP; plan integration with a secrets manager for production.  
- TLS: terminate at reverse proxy; enforce HTTPS and HSTS.  
- Backups: automated DB dumps and object store replication.  
- Monitoring: Prometheus exporters and health probes; SLOs for scan completion and API latency.

CI/CD and release strategy:

- Build pipeline: container images built on merge; automated tests (unit/integration); image signing for production.  
- Deployments: rolling or blue-green deployments for the API; workers rolled with job draining.  
- Migrations: run DB migrations as part of deployment pipeline with pre-checks and post-rollback strategies.

High availability & resilience (future):

- Multi-AZ DB with read replicas, queue cluster, and cross-region object replication.
- Leader-election for scheduled workflow runners.

## Appendix: Risks and Mitigations

- Running third-party scanners exposes the host to malformed inputs and tool vulnerabilities. Mitigation: sandbox plugins, run tools with limited privileges, and scan outputs before ingestion.
- Data explosion from raw scan artifacts. Mitigation: retention policies, configurable artifact sampling, and offloading to object storage.
- Long-running workflows and retries may queue up. Mitigation: backpressure mechanisms, per-customer quotas, and graceful job throttling.

## Next steps

- Review this architecture with stakeholders for alignment.  
- Validate sandbox choices for plugin execution.  
- Prototype the lightweight workflow engine to validate state model and guarantees.

---
Generated by the Principal Architect for AegisX.
