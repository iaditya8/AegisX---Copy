# Sprint Review Log

This document records the results, tests, risks, and lessons learned for each sprint in AegisX.

## Sprint 1

- **Status**: Approved
- **Date**: 2026-06-11
- **Tests**: 
  - 4 integration tests covering liveness (`/healthz`) and readiness (`/readyz`) endpoints under successful and mock-failed PostgreSQL/Redis connectivity.
  - Automated formatting and lint verification (`ruff`, `black`).
- **Risks**:
  - Lack of direct Docker/PostgreSQL access on the development host. This could mask configuration or dialect translation issues at deployment time.
- **Lessons Learned**:
  - Setting up modular and test-friendly dependency overrides early in the codebase lifecycle (e.g., mock databases in `conftest.py`) ensures that test suites can execute and validate application routes reliably in clean environments like CI/CD systems.

---

## Sprint 2

- **Status**: Approved
- **Date**: 2026-06-11
- **Tests**:
  - 19 integration and unit tests total.
  - Verification of credentials validation (`POST /api/v1/auth/token`).
  - Verification of token refresh rotation and verification payload formats (`POST /api/v1/auth/refresh`).
  - Enforcement of RBAC roles (Admin, Analyst, Viewer) across CRUD resources.
  - Verification of API key generation (`POST /api/v1/users/{id}/api-key`) and custom API key header checks (`X-API-Key`).
- **Risks**:
  - API keys are returned raw only once to the client upon generation; loss of this key requires a roll. Secret keys and token durations must be securely managed via env variables.
- **Lessons Learned**:
  - Python's `unittest.mock.patch` requires patching the specific namespace where a class or function is imported and executed, rather than the library namespace where it is defined. Adhering to this avoids subtle test validation issues.

---

## Sprint 3

- **Status**: Approved
- **Date**: 2026-06-12
- **Tests**:
  - 21 new integration and unit tests covering Scope CRUD, Asset listing/filtering, Asset relationships, Asset history, Audit logging, parent scope deletion asset hiding, and cross-scope tenant segregation.
  - Total test suite counts 40 passed tests.
  - Automated formatting and lint verification (`ruff`).
- **Risks**:
  - High complexity in validating asset ownership via parent scope lookup. Developers must always execute this check prior to exposing any asset metadata.
- **Lessons Learned**:
  - Separation of service-level database commits allows isolation of auditing/history tracking tasks. Using mock DB sessions in tests guarantees logic assertions without physical database constraints.

---

## Sprint 4

- **Status**: Approved
- **Date**: 2026-06-12
- **Tests**:
  - 12 new integration and unit tests covering Workflow CRUD, Pydantic validations, Celery eager-mode background task execution, lifecycle state transitions, cancellation, event emission with correlation ID tracing, and cross-resource scope/workflow ownership validation check.
  - Total test suite counts 52 passed tests.
  - Automated formatting and lint verification (`ruff`).
- **Risks**:
  - Celery background workers run out of API scope. DB access logic must be handled using safe async wrappers to avoid connection pool leaks.
- **Lessons Learned**:
  - Running async database code inside synchronous Celery worker threads is safest when executing in separate, dedicated threads. This prevents asyncio event loop conflicts during unit/integration tests.


