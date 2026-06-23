# Sprint 13 — Implementation Plan

> **Paste your implementation plan for Sprint 13 below this line.**
> Delete this placeholder text when adding your content.

# Sprint 13: Remediation Intelligence & Workflow Management

This sprint transforms AegisX from an Exposure Decision Support Platform into a Remediation Intelligence Platform. It introduces remediation tracking, ownership, status management, SLA monitoring, exception handling, and remediation history, all while strictly adhering to registry-driven logic and remaining fully compatible with previous sprints.

## Mandatory Compatibility Validation

Before implementation, ensure full compatibility with Sprint 7–12 services, snapshots, registries, workflow events, audit mechanisms, and cache layers.

The implementation must:
- Reuse `RecommendationFingerprintService` from Sprint 12.
- Reuse `RecommendationHistoryService` where applicable.
- Reuse `WorkflowEventService`.
- Reuse `AuditService`.
- Reuse existing ownership validation patterns.
- Reuse existing snapshot rebuild patterns established in `CorrelationSnapshotService`, `RecommendationSnapshotService`, and Report Cache Services.

Do not create duplicate ownership, audit, event, fingerprint, aging, or cache mechanisms. Extend existing architecture only.

## Proposed Changes

---

### Core Domain Models

#### [NEW] `backend/src/domain/entities/remediation.py`
- Create `RemediationStatus` enum (`OPEN`, `IN_PROGRESS`, `REMEDIATED`, `ACCEPTED_RISK`, `FALSE_POSITIVE`, `DEFERRED`).
- Create `RemediationHistoryType` enum (`STATUS_CHANGE`, `OWNER_CHANGE`, `SLA_BREACH`, `EXCEPTION`, `CREATED`).
- Create `RemediationResponse` Pydantic model:
```python
{
  "remediation_id": "uuid",
  "recommendation_fingerprint": "sha256",
  "recommendation_id": "...",
  "status": "OPEN",
  "owner": "...",
  "due_date": "...",
  "created_at": "...",
  "updated_at": "...",
  "reason": None
}
```
- **Remediation Identity**: The recommendation fingerprint is the remediation anchor. Remediation identity remains independent (UUID). One active remediation may exist per recommendation fingerprint.
- Create Exception tracking models (`RemediationException`, `RemediationHistoryEntry`).
- Create `OwnerAssignmentModel` to track explicit ownership changes (`old_owner`, `new_owner`, `timestamp`).

---

### Registries

#### [NEW] `backend/src/services/remediation_sla_registry.py`
- Implement `SLA_DAYS` mapping priorities (`CRITICAL`: 7, `HIGH`: 30, `MEDIUM`: 60, `LOW`: 90) strictly to avoid hardcoded logic elsewhere.

---

### Services

#### [NEW] `backend/src/services/remediation_service.py`
- Handles standard lifecycle actions: `create_remediation()`, `update_status()`, `assign_owner()`, `accept_risk()`, `mark_false_positive()`, `defer_remediation()`, `close_remediation()`, `get_remediation()`.

- **Recommendation → Remediation Auto-Creation**
  - Whenever a new recommendation is created, `RemediationService` MUST automatically create an `OPEN` remediation record.
  - Recommendation creation is the authoritative start point of remediation lifecycle tracking. This prevents blind spots and starts SLA tracking immediately.

- **Remediation Lifecycle Rules** (State Machine) with strict transition validations:
  - `OPEN` ├─> `IN_PROGRESS`, `ACCEPTED_RISK`, `FALSE_POSITIVE`, `DEFERRED`
  - `IN_PROGRESS` ├─> `REMEDIATED`, `ACCEPTED_RISK`, `DEFERRED`
  - `DEFERRED` ├─> `IN_PROGRESS`, `ACCEPTED_RISK`
  - `REMEDIATED` └─ terminal
  - `FALSE_POSITIVE` └─ terminal
  - `ACCEPTED_RISK` └─ terminal
  - Invalid transitions raise validation errors.

- **Remediation Reopen Rules**
  - Terminal remediation states remain terminal.
  - A new remediation may only be created if:
    1. The recommendation fingerprint changes, OR
    2. The underlying finding fingerprint changes, OR
    3. The recommendation was previously closed and a rediscovered finding creates a new recommendation fingerprint.
  - This keeps history, aging, and audit intact while supporting rediscovered issues.
  
- **Recommendation Synchronization Rule**
  - If a recommendation is recomputed but retains the same recommendation fingerprint:
    - Do not create a new remediation.
    - Preserve remediation UUID.
    - Preserve remediation history.
    - Preserve remediation ownership.
    - Preserve remediation SLA history.
    - Update only recommendation-derived fields if required.
  - The recommendation fingerprint remains the authoritative link between recommendation lifecycle and remediation lifecycle.

- Invokes Workflow/Audit logic internally.

#### [NEW] `backend/src/services/remediation_aging_service.py`
- Provide `get_age_days()`, `get_overdue_items()`, and `get_sla_breaches()`.
- Uses `created_at`, `updated_at`, and `last_status_change` from remediations.

#### [NEW] `backend/src/services/sla_monitoring_service.py`
- Expose methods that calculate `Within SLA`, `Approaching SLA`, and `Breached SLA` using the `SLA_DAYS` registry.
- Computes `days_remaining`.

#### [NEW] `backend/src/services/exception_service.py`
- Handles logic for `accept_risk()`, `false_positive()`, and `defer()`.
- Records justifications (`reason`, `approved_by`, `timestamp`).
- Broadcasts corresponding workflow events and audit entries.

#### [NEW] `backend/src/services/remediation_snapshot_service.py`
- Track `open`, `in_progress`, `remediated`, `accepted_risk`, `false_positive`, `deferred`, `overdue`, and `sla_breached` counts per `asset_id` in an in-memory dictionary.
- **Snapshot Consistency Requirement**: Snapshots must be derived from active remediation state and never act as the source of truth. If a snapshot entry is missing or invalid, `generate_snapshot(asset_id)` must rebuild it from remediation records. Snapshots should always be caches.
- Implements `generate_snapshot(asset_id)`, `update_snapshot(asset_id)`, `get_snapshot(asset_id)`.

#### [NEW] `backend/src/services/remediation_history_service.py`
- In-memory history tracking for status changes, explicit owner changes, SLA breaches, and exceptions. Uses `RemediationHistoryType` to strongly type history records.

---

### Integrations & API

#### [NEW] `backend/src/api/v1/routers/remediations.py`
- Defines standard REST endpoints: `GET` by asset, `GET` by id, and `POST` for actions (`assign`, `start`, `complete`, `accept-risk`, `false-positive`, `defer`).
- All endpoints perform proper RBAC verification and return standard JSON schemas.

#### [MODIFY] `backend/src/worker.py`
- Hook `RemediationSnapshotService` refresh handlers into recommendation updates, priority changes, finding changes, and risk changes. Provide exception handling to ensure Celery never crashes.
- Intercept new recommendations and trigger `create_remediation` automatically.

#### [MODIFY] AI Copilot Integrations
- `backend/src/services/asset_copilot_service.py`
- `backend/src/services/finding_copilot_service.py`
- `backend/src/services/executive_copilot_service.py`
- Inject remediation metrics/snapshots as read-only context to allow AI to explain remediation status without modifying it.

#### [MODIFY] Workflow / Audit Services
- Ensure new workflow events are routed via `WorkflowEventService`.
- Events: `remediation.created`, `remediation.started`, `remediation.completed`, `remediation.accepted_risk`, `remediation.false_positive`, `remediation.deferred`, `remediation.sla_breached`.
- Ownership Events: `remediation.assigned`, `remediation.reassigned`.
- Hook in `AuditService` calls on any remediation state mutation.

---

## Verification Plan

### Automated Tests
- Create `backend/tests/integration/test_remediation.py` to cover:
  - Remediation Lifecycle (Creation, assignment, completion, closure).
  - State Machine valid and invalid transitions (`test_invalid_status_transition`).
  - Terminal State Enforcement (`test_remediation_terminal_state_enforcement`): Verify `REMEDIATED -> IN_PROGRESS` raises a `ValidationError` while leaving history, audit, and workflow unchanged.
  - Auto-creation (`test_auto_remediation_creation`): Verify Recommendation Created -> Remediation Auto-Created -> OPEN -> Due Date Calculated -> SLA Tracking.
  - Fingerprinting (Recommendation linkage, duplicate prevention).
  - SLA & Aging (Calculations, breach detection, overdue tracking).
  - Exception paths (Risk acceptance, FP, deferrals).
  - Snapshots (Generation, updates, breached counts).
  - Snapshot rebuild consistency (`test_snapshot_rebuild_consistency`): Verify snapshot can be correctly rebuilt from active records if deleted.
  - Workflows and AI context validation.
  - Stability tests against missing remediations and empty datasets.
- Ensure minimum coverage >= 85%.

### Post-Implementation Checks
- Run `pytest backend/tests/integration/test_remediation.py`
- Run `pytest`
- Run `ruff check backend/`
- Run `black backend/`


Implementation Requirement

This sprint must preserve backwards compatibility with all
existing tests from Sprint 7–12.

No existing public API response schema may be modified.

No existing workflow event names may be modified.

No existing audit payload formats may be modified.

New functionality must be additive only.

A full regression suite execution is mandatory before completion.