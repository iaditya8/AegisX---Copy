# Backend Architecture Details

This document outlines the low-level component interactions for the AegisX MVP backend, specifically focusing on how FastAPI, Celery, PostgreSQL, and Plugins coordinate to fulfill security workflows.

## System Topology

```text
+-------------------+      +-----------------------+      +-----------------------+
|   Client (UI)     | ---> |  API Gateway (Nginx)  | ---> |   FastAPI App Layer   |
+-------------------+      +-----------------------+      +-----------------------+
                                                              |      |
                                                              v      v
                                             +----------------+    +----------------+
                                             |  PostgreSQL DB |    |  Redis Broker  |
                                             +----------------+    +----------------+
                                                     ^                     ^
                                                     |                     |
                                             +--------------------------------------+
                                             |        Celery Worker Layer           |
                                             | +-----------------+ +--------------+ |
                                             | | Workflow Engine | | Plugin Host  | |
                                             | +-----------------+ +--------------+ |
                                             +--------------------------------------+
```

## 1. FastAPI Application Layer

- **Framework:** FastAPI with Pydantic for strict request/response validation.
- **Concurrency:** Uses `async/await` for HTTP request handling and database querying (via asyncpg or async SQLAlchemy session).
- **Responsibility:** Handles Auth (JWT + RBAC), input validation, CRUD operations on core models (Users, Scopes), and dispatching jobs to the message broker.
- **Limits:** NEVER runs heavy blocking computations or subprocesses.

## 2. Celery Worker Layer & Workflow Engine

- **Framework:** Celery running in independent container instances.
- **Broker:** Redis handles task distribution.
- **Result Backend:** PostgreSQL/Redis for storing task completion statuses.
- **Workflow State Machine:** 
  The Workflow Engine runs inside Celery. When FastAPI triggers a scan, it drops a message in Redis. Celery picks it up and begins a "Task Chain":
  1. **Job Dispatch:** `run_recon_job(workflow_id)`
  2. **Wait & Poll:** Engine waits for recon tools to finish.
  3. **Event Emission:** Engine fires canonical events (e.g., `scan.completed`).
  4. **Job Chain:** Engine triggers `run_nuclei_job(scope_id)`.

## 3. Plugin Host (Sandboxing)

Security tools (`nuclei`, `subfinder`, etc.) are untrusted and volatile. The Plugin Host ensures they cannot crash the main worker node.

- **Execution Model:** Subprocess `Popen` with strict resource limits.
- **Timeouts:** Every plugin execution receives a hard timeout (e.g., 60 minutes). If exceeded, the process group is killed (`SIGKILL`).
- **Memory/CPU Constraints:** (Linux native or cgroups) limits memory allocation per scanner.
- **Output Parsing:** Plugins stream stdout/stderr. A Python adapter parses the JSON lines dynamically to avoid memory bloat, emitting a `Canonical Event` (e.g., `finding.created`) for each discovered vulnerability immediately.

## 4. The Canonical Event Bus

Internal communication happens via structured events.

- **Mechanism:** Redis Pub/Sub or Celery task events.
- **Format:** Strict JSON schema conforming to the models defined in `Docs/03_Architecture.md` (Canonical Event Model).
- **Idempotency:** The worker consuming these events (e.g., inserting a finding to PostgreSQL) must use upsert (`ON CONFLICT (fingerprint) DO UPDATE`) to handle duplicate events gracefully.

## 5. PostgreSQL Persistence Layer

- **Transactions:** Complex operations (e.g., updating workflow state and logging an audit event) must be wrapped in a single database transaction. If Celery fails mid-job, the state rolls back.
- **Migrations:** Managed by Alembic. The API and Workers must always be deployed in sync with the database schema version.

---
Prepared by the Principal Software Architect for AegisX.
