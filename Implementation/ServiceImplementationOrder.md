# Service Implementation Order

This document details the step-by-step dependency-ordered roadmap for AI agents and human contributors implementing the AegisX MVP backend. Strict adherence to this order ensures no team or agent is blocked by missing dependencies.

## Phase 1: Core Foundation (The Skeleton)

**Goal:** Provide the underlying configuration, logging, and database access layer for all future services.
**Dependencies:** None.

1. **Project Skeleton & Configuration:**
   - Create `backend/src/core/config.py` using Pydantic Settings.
   - Implement structured JSON logging in `backend/src/core/logging.py`.
   - Setup `main.py` with FastAPI initialization and global exception handlers.
2. **Database & ORM:**
   - Configure PostgreSQL session factory (`session.py`).
   - Implement base SQLAlchemy models following the `Docs/04_Database.md` schema.
   - Generate the initial Alembic migration scripts (`rev_001` through `rev_004`).
3. **Domain & Repositories:**
   - Define Pydantic Entities in `src/domain/entities/`.
   - Implement base repository protocols and their SQLAlchemy counterparts in `src/infrastructure/repositories/`.

## Phase 2: Auth & API Basics (The Frontend Gateway)

**Goal:** Secure the API and provide basic CRUD for users and targets.
**Dependencies:** Phase 1 (Database models).

1. **Authentication Service:**
   - Implement JWT generation and validation (`core/security.py`).
   - Create the Auth service (`services/auth_service.py`) for login and RBAC.
   - Build `/api/v1/auth/token` and `/api/v1/auth/refresh` endpoints.
2. **User & Scope Management:**
   - Implement API endpoints for Users (`/api/v1/users`).
   - Implement API endpoints for Scopes (`/api/v1/scopes`).
   - Build underlying services handling soft deletion and validation.

## Phase 3: Task Orchestration (The Engine)

**Goal:** Establish the asynchronous background processing layer.
**Dependencies:** Phase 1 (Config, Logging).

1. **Celery Infrastructure:**
   - Configure Celery app with Redis broker and PostgreSQL/Redis result backend (`infrastructure/celery/worker.py`).
   - Implement a generic Celery task runner.
2. **Event Bus Definition:**
   - Implement event publishing interfaces for the Canonical Event Model (e.g., `asset.discovered`).

## Phase 4: Plugin Framework (The Extensions)

**Goal:** Build the secure sandbox environment for external scanners.
**Dependencies:** Phase 3 (Celery basics).

1. **Plugin Host:**
   - Define the `PluginWrapper` interface.
   - Implement Subprocess sandboxing using generic OS constraints.
   - Build the Plugin state management API (`/api/v1/plugins`).
2. **Recon Plugins:**
   - Wrap `subfinder` and `amass`.
   - Implement JSON parsers to emit `asset.discovered` events.
3. **Scanning Plugins:**
   - Wrap `nuclei` and `httpx`.
   - Implement parsers to emit `finding.created` events.

## Phase 5: Workflow State Machine (The Brain)

**Goal:** Tie API requests to plugin execution through a durable state machine.
**Dependencies:** Phase 2 (API), Phase 3 (Celery), Phase 4 (Plugins).

1. **Workflow Service:**
   - Implement the business logic for creating and starting workflows (`services/workflows.py`).
   - Expose `/api/v1/workflows` endpoints.
2. **Job Coordination:**
   - Write Celery task chains: Trigger Recon -> Wait for completion -> Trigger Nuclei.
   - Persist Workflow Events to the `workflow_events` table as jobs progress.

## Phase 6: Findings & Reporting (The Output)

**Goal:** Expose the scan results and generate artifacts.
**Dependencies:** Phase 5 (Workflows generating findings).

1. **Findings API:**
   - Implement `/api/v1/findings` and pagination logic.
2. **Correlation Service (MVP Stub):**
   - Implement basic deduplication logic when inserting findings to prevent noise.
3. **Reporting:**
   - Implement Markdown/HTML report generation from findings.
   - Expose `/api/v1/reports` endpoints.

---
Prepared by the Principal Software Architect for AegisX.
