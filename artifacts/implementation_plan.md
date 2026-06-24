# Implementation Plan — Sprint 15: Continuous Monitoring & Posture Drift Intelligence

This sprint transforms AegisX from a Governance & Compliance platform into a **Continuous Monitoring & Posture Drift Intelligence Platform**. It introduces a passive, in-memory monitoring and drift detection layer that tracks state transitions (additions, modifications, resolutions, score changes, and compliance statuses) over time.

## User Review Required

> [!IMPORTANT]
> **In-Memory Posture History**: Following the platform patterns, all monitoring events, baseline caches, and snapshots will be maintained **strictly in-memory** to avoid database migrations.
>
> **Dynamic Rebuild Engine**: If baseline states or snapshot statistics are cleared from memory, they are automatically rebuilt on-demand by traversing the historical list of monitoring events.

## Open Questions

> [!IMPORTANT]
> **Question 1**: For risk scoring drift detection, we define specific thresholds (15.0 for increase/decrease, 75.0 for critical boundary). Do you approve these threshold values?

## Proposed Changes

---

### Core Domain Models

#### [NEW] [monitoring.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/domain/entities/monitoring.py)
Defines the Pydantic schemas and classes for the monitoring layer:
- `MonitoringEvent`: Class representing an individual monitoring event with attributes (`event_id`, `change_type`, `asset_id`, `finding_id`, `previous_state`, `current_state`, `timestamp`, `fingerprint`).
- `MonitoringEventResponse`: Pydantic schema for API serialization.
- `MonitoringSnapshotResponse`: Pydantic schema for platform-wide monitoring statistics.

---

### Monitoring & Drift Services

#### [NEW] [monitoring_fingerprint_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/monitoring_fingerprint_service.py)
- Computes stable event hashes to prevent duplicate logging:
  `SHA256(change_type + str(asset_id) + str(finding_id) + str(previous_state) + str(current_state))`

#### [NEW] [baseline_state_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/baseline_state_service.py)
- Manages baseline caches for asset information, findings status, risk scores, and governance status.
- Implements dynamic rebuild rules to reconstruct baseline caches from the `MonitoringEvent` history log.

#### [NEW] [continuous_refresh_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/continuous_refresh_service.py)
- Compares current scanner findings, asset details, risk scores, and compliance states against captured baselines.
- Emits monitoring events on asset drift (`ASSET_ADDED`, `ASSET_MODIFIED`, `ASSET_REMOVED`), finding drift (`FINDING_ADDED`, `FINDING_RESOLVED`, `FINDING_REDISCOVERED`), risk drift (score increases/decreases >= 15.0, or crossing the critical 75.0 boundary), and compliance drift.

#### [NEW] [monitoring_snapshot_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/monitoring_snapshot_service.py)
- Caches cumulative monitoring metrics (e.g., total added assets, resolved findings, etc.) in-memory.
- Rebuilds dynamically from events history if the cache is lost.

---

### Routing & Integrations

#### [NEW] [monitoring.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/api/v1/routers/monitoring.py)
- Exposes continuous monitoring endpoints with RBAC checks and scope-level filtering:
  - `GET /api/v1/monitoring/events`
  - `GET /api/v1/monitoring/assets/{id}`
  - `GET /api/v1/monitoring/findings/{id}`
  - `GET /api/v1/monitoring/summary`
  - `GET /api/v1/monitoring/drift/assets`
  - `GET /api/v1/monitoring/drift/findings`
  - `GET /api/v1/monitoring/drift/risk`
  - `GET /api/v1/monitoring/drift/governance`

#### [MODIFY] [main.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/main.py)
- Register the new `monitoring_router`.

#### [MODIFY] [worker.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/infrastructure/celery/worker.py)
- Refreshes monitoring states dynamically (`ContinuousRefreshService.refresh_all(db)`) at the end of each scan execution pipeline step.

#### [MODIFY] [ai_context_builder.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_context_builder.py)
- Injects monitoring details (`monitoring_events`, `asset_drift`, `finding_drift`, `risk_drift`, `governance_drift`) into asset, finding, and executive prompt contexts.

---

## Verification Plan

### Automated Tests
- Create `backend/tests/integration/test_monitoring.py` containing:
  - Asset, finding, and risk drift detection validation.
  - Compliance drift and governance acceptance expiration detection.
  - Snapshot and baseline dynamic regeneration.
  - AI Copilot context injection checks.
  - RBAC checks and scope filtering.
  - Celery task worker integration.
  - Event fingerprint deduplication.
- Run tests:
  ```powershell
  .venv\Scripts\pytest
  ```
- Formatting & Linting checks:
  ```powershell
  .venv\Scripts\ruff check backend/
  .venv\Scripts\black --check backend/
  ```

### Manual Verification
- None required; verified entirely via integration tests.
