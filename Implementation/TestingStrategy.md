# Testing Strategy

This document establishes the testing framework and quality assurance protocols for the AegisX platform. All agents and contributors must ensure code passes these criteria before merging.

## Testing Layers

### 1. Unit Testing (Pytest)
- **Scope:** Domain entities, Core utilities, Parsers, and isolated Services.
- **Rules:**
  - Mock external dependencies (Databases, Redis, File System) using `unittest.mock` or pytest fixtures.
  - Test edge cases and failure modes explicitly.
- **Coverage Target:** >80% code coverage.

### 2. Integration Testing
- **Scope:** API Endpoints (FastAPI Routers), Database Repositories, Celery Tasks.
- **Rules:**
  - Use `TestClient` from `fastapi.testclient` to invoke endpoints.
  - Tests must run against a real, isolated PostgreSQL database (e.g., using a testcontainer or a dedicated `test` database spun up in CI).
  - Test database must be wiped or rolled back after each test function.
  - Do NOT hit real external network targets (mock DNS, HTTP requests).

### 3. Plugin Testing
- **Scope:** Scanner and Recon plugins (`subfinder`, `nuclei`, etc.).
- **Rules:**
  - Do not run the actual binary if it requires network access.
  - Instead, use mock stdout/stderr payloads captured from real runs to test the parsing and event emission logic.
  - Verify that the Sandbox enforces timeout rules by testing the wrapper against a simulated infinite loop script.

### 4. End-to-End (E2E) Testing (Future Phase)
- **Scope:** The entire workflow from Scope creation -> Discovery -> Scanning -> Reporting.
- **Rules:**
  - Run the full stack locally via Docker Compose.
  - Trigger a scan against a local intentionally vulnerable container (e.g., a purposefully insecure Nginx container).
  - Assert that specific findings are generated in the database.

## Security & Static Analysis

Running locally and gated in CI/CD:

1. **Linting & Formatting:**
   - `ruff` and `black` for formatting.
   - `mypy` for strict type checking.
2. **SAST (Static Application Security Testing):**
   - `bandit` to scan Python code for hardcoded secrets, unsafe `eval()`, or insecure subprocess usage.
3. **Dependency Scanning (SCA):**
   - `safety` or `trivy` to check `requirements.txt` for known CVEs.

## Continuous Integration (CI) Pipeline

Every Pull Request must pass the following GitHub Actions jobs:
- `linting`: Runs Ruff, Black, Mypy.
- `security-scan`: Runs Bandit and Trivy.
- `unit-tests`: Runs pytest with coverage reporting.
- `integration-tests`: Spins up Postgres service, applies Alembic migrations, runs API tests.

No merge to `main` is permitted if any CI job fails.

---
Prepared by the Principal Software Architect for AegisX.
