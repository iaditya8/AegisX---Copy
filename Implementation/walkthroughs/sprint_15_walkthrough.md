# Sprint 15 — Walkthrough

> **Paste your walkthrough for Sprint 15 below this line.**
> Delete this placeholder text when adding your content.

# Walkthrough: Continuous Monitoring & Intelligence Refresh (Sprint 15)

AegisX has now evolved into a **Continuous Monitoring & Intelligence Refresh Platform** by introducing a passive, read-only monitoring layer that detects drift across assets, findings, risks, and governance states.

## Key Accomplishments

### 1. Deterministic Event Fingerprinting (`monitoring_fingerprint_service.py`)
To prevent event flooding and duplicate logs across continuous refresh runs, we introduced deterministic fingerprinting:
- **Fingerprint Formula**: `SHA256(change_type, asset_id, finding_id, previous_state, current_state)`
- Repeated refresh cycles and redundant state checks produce the same fingerprint, ensuring that events are idempotent and history remains perfectly stable.

### 2. Baseline State Service (`baseline_state_service.py`)
Drift detection compares current state against baseline records rather than current state itself:
- Methods: `capture_asset_baseline()`, `capture_finding_baseline()`, `capture_risk_baseline()`, `capture_governance_baseline()`.
- **Dynamic Rebuild**: If a baseline cache is cleared, it automatically reconstructs itself from the monitoring events history, preventing data loss.

### 3. Continuous Refresh Engine & Drift Detection (`continuous_refresh_service.py`)
Orchestrates change checks across all monitored resources:
- Compares new discovery and vulnerability scans against baseline records.
- Detects new, modified, or removed assets and open, resolved, or rediscovered findings.
- Tracks risk score changes and triggers alerts if they cross defined increase/decrease (15.0) or critical (75.0) thresholds.
- Tracks compliance changes (failure, restoration, or risk acceptance expiration).

### 4. Cache-Only Snapshots (`monitoring_snapshot_service.py`)
Aggregates monitoring metrics (added assets, resolved findings, risk drifts, etc.) in a memory cache:
- Like the baselines, snapshots are purely cache-level and rebuild dynamically from the event history if deleted or lost.

### 5. API Gateway Routers (`api/v1/routers/monitoring.py`)
Exposes read-only REST endpoints under `/api/v1/monitoring`:
- Ends include: `/events`, `/assets/{id}`, `/findings/{id}`, `/summary`, and drift details for `/drift/assets`, `/drift/findings`, `/drift/risk`, `/drift/governance`.
- **RBAC & Scope Restriction**: Only admins and operators can fetch events, and operators are dynamically filtered by scope ownership. All endpoints use `StandardResponse`.

### 6. AI Copilot Enrichment
- Injects `monitoring_events`, `asset_drift`, `finding_drift`, `risk_drift`, and `governance_drift` context variables directly into prompt contexts for asset, finding, and executive contexts, allowing the AI Copilot to explain posture changes dynamically.

### 7. Celery Worker Integration
- The Celery worker runs `ContinuousRefreshService.refresh_all(db)` at the end of every scan step, wrapped in a graceful try-except block to prevent task failure.

---

## Verification Results

### 1. Verification Test Suite
We implemented **23 integration tests** covering all monitoring facets:
- Asset, finding, and risk drift detection (1-9)
- Governance compliance change and expiration tracking (10-12)
- Snapshot and baseline dynamic regeneration (13-14, 21, 23)
- AI Copilot context injection (15)
- RBAC and scope validation (16-17)
- Worker task completion and failure recovery (18-19)
- Event deduplication and state change assertions (20, 22)

All **23 tests passed successfully** in **0.26 seconds**:
```bash
backend\tests\integration\test_monitoring.py .......................     [100%]
======================= 23 passed in 0.26s ========================
```

### 2. Full Regression Validation
We executed the entire integration test suite to verify Sprints 7-14 compatibility. **All 278 tests passed successfully** with zero regressions:
```bash
====================== 278 passed in 11.74s ======================
```



