# Sprint 16 — Implementation Plan

> **Paste your implementation plan for Sprint 16 below this line.**
> Delete this placeholder text when adding your content.

# Sprint 16 Implementation Plan: SOC Operations & Alert Management

AegisX will be transformed from a Continuous Monitoring Platform into a SOC Operations Intelligence Platform. Sprint 16 introduces an operational alert management layer that acts upon continuous monitoring events, governance drift events, SLA breaches, and risk acceptance expirations to generate, deduplicate, escalate, and assign alerts to analysts.

## User Review Required

> [!IMPORTANT]
> **Advisory-Only AI**: The AI Security Copilot is strictly advisory. It can explain alert details, reasons, and severities, but is physically blocked from mutating alert states (creating, updating, assigning, closing, or suppressing alerts).
> 
> **In-Memory Operations**: Alert management utilizes in-memory registries and stores to avoid database migrations, mirroring the patterns established in prior sprints (remediations, risk acceptances, and snapshots).
> 
> **Dynamic Rebuild Pattern**: Alert snapshots and statistics are cache-only. If lost, they are fully reconstructed dynamically by traversing past monitoring events and alerts.

## Open Questions

*No open questions are identified; the requirements are fully specified and backward compatible with Sprints 7-15.*

---

## Proposed Changes

### Domain Models

#### [NEW] [alert.py](file:///c:/Users/Aditya/AegisX/backend/src/domain/entities/alert.py)
Create domain definitions for alert modeling:
- `AlertSeverity(str, Enum)`: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- `AlertStatus(str, Enum)`: `OPEN`, `ACKNOWLEDGED`, `IN_PROGRESS`, `ESCALATED`, `RESOLVED`, `SUPPRESSED`
- `AlertType(str, Enum)`: `ASSET_DRIFT`, `FINDING_DRIFT`, `RISK_DRIFT`, `COMPLIANCE_DRIFT`, `RISK_ACCEPTANCE_EXPIRATION`, `SLA_BREACH`, `CRITICAL_FINDING`
- `AlertResponse`: Pydantic model containing `alert_id`, `alert_fingerprint`, `alert_type`, `severity`, `status`, `asset_id`, `finding_id`, `recommendation_id`, `remediation_id`, `created_at`, `updated_at`, `owner`, `title`, and `description`.

---

### Registries & Fingerprinting

#### [NEW] [alert_severity_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/alert_severity_registry.py)
- Map `AlertType` dynamically to their corresponding `AlertSeverity`:
  - `CRITICAL_FINDING` -> `CRITICAL`
  - `RISK_ACCEPTANCE_EXPIRATION` -> `HIGH`
  - `SLA_BREACH` -> `HIGH`
  - `COMPLIANCE_DRIFT` -> `HIGH`
  - `RISK_DRIFT` -> `MEDIUM`
  - `FINDING_DRIFT` -> `MEDIUM`
  - `ASSET_DRIFT` -> `LOW`

#### [NEW] [alert_fingerprint_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/alert_fingerprint_service.py)
- Generates stable, deterministic fingerprints to prevent duplicates:
  `SHA256(alert_type, asset_id, finding_id, recommendation_id, remediation_id)`

##### Alert Fingerprint Stability Requirements
The alert fingerprint must remain stable across:
- Worker refresh cycles
- Monitoring refresh cycles
- Alert ownership changes
- Alert acknowledgements
- Alert escalations
- Alert lifecycle transitions

The alert fingerprint must only change when:
- `alert_type` changes
- `asset_id` changes
- `finding_id` changes
- `recommendation_id` changes
- `remediation_id` changes

`alert_severity` and `alert_status` must never be included in the fingerprint. This prevents duplicate alert creation and preserves alert history, ownership, aging, and escalation tracking.

---

### Core Services

#### [NEW] [alert_generation_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/alert_generation_service.py)
- Consumes monitoring events, governance drift, SLA breaches, and expirations.
- Uses `AlertFingerprintService` to deduplicate incoming alerts.
- Emits `alert.created` workflow events and logs to `AuditService`.

#### [NEW] [alert_lifecycle_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/alert_lifecycle_service.py)
- Implements alert state machine transitions:
  - `OPEN` -> `ACKNOWLEDGED` or `SUPPRESSED`
  - `ACKNOWLEDGED` -> `IN_PROGRESS` or `RESOLVED`
  - `IN_PROGRESS` -> `ESCALATED` or `RESOLVED`
  - `ESCALATED` -> `RESOLVED`
  - Enforces terminal status for `RESOLVED` and `SUPPRESSED`.

##### Alert Terminal State Enforcement
- `RESOLVED` -> terminal
- `SUPPRESSED` -> terminal

Requirements:
- Alerts in terminal states cannot be reopened.
- Monitoring refreshes producing the same fingerprint must not reopen terminal alerts.
- A new alert may only be created if:
  - alert fingerprint changes, OR
  - underlying monitoring event fingerprint changes, OR
  - a new drift event creates a new alert context.

This preserves alert history and prevents endless alert reopen loops.
This is the exact equivalent of Sprint 13 Remediation Terminal State Enforcement and Sprint 14 Risk Acceptance Expiration Rules, keeping lifecycle behavior consistent.

##### Alert Synchronization Rule
If a monitoring event is reprocessed and produces the same alert fingerprint:
- Do not create a new alert.
- Preserve `alert_id`.
- Preserve ownership.
- Preserve alert history.
- Preserve escalation history.
- Preserve timestamps.
Only update mutable alert metadata when required.

#### [NEW] [alert_queue_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/alert_queue_service.py)
- Tracks alert assignments, analyst workloads, and aggregates queue stats (open/escalated alert counts).

#### [NEW] [alert_escalation_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/alert_escalation_registry.py)
- Map `AlertSeverity` to escalation aging thresholds:
  - `CRITICAL` -> 1 day
  - `HIGH` -> 3 days
  - `MEDIUM` -> 7 days
  - `LOW` -> 14 days

#### [NEW] [alert_escalation_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/alert_escalation_service.py)
- Runs checks on open/acknowledged/in-progress alerts, auto-escalates aging alerts, and emits `alert.escalated` workflow events.

#### [NEW] [alert_snapshot_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/alert_snapshot_service.py)
- Memory-cached snapshots tracking alert status and severity counts.
- Rebuilds dynamically from raw alert records if cache lookup fails.

##### Alert Snapshot Consistency Requirement
Snapshots must never be treated as the source of truth.
`AlertSnapshotService` must derive all statistics from active alert records.
If a snapshot cache entry is missing, corrupted, or deleted, `generate_snapshot()` and `get_snapshot()` must rebuild the snapshot from active alert records.
Snapshots are cache-only structures and must not store any state that cannot be reconstructed.

---

### Integrations

#### [MODIFY] [worker.py](file:///c:/Users/Aditya/AegisX/backend/src/infrastructure/celery/worker.py)
- At the end of workflow scan steps, invoke `AlertGenerationService.generate_alerts(db)` and `AlertEscalationService.process_escalations(db)` gracefully.

#### [MODIFY] [ai_context_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_context_builder.py)
- Inject `alert_summary`, `active_alerts`, `critical_alerts`, `escalated_alerts`, and `owned_alerts` into prompt context payloads.

#### [MODIFY] [asset_copilot_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/asset_copilot_service.py), [finding_copilot_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/finding_copilot_service.py), [executive_copilot_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/executive_copilot_service.py)
- Document alert constraints within Copilot modules.

#### [MODIFY] [ai_prompt_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_prompt_builder.py)
- Embed system constraints on AI advisor-only alert role in prompts.

---

### API Gateway

#### [NEW] [alerts.py](file:///c:/Users/Aditya/AegisX/backend/src/api/v1/routers/alerts.py)
Exposes REST endpoints:
- `GET /api/v1/alerts`
- `GET /api/v1/alerts/{id}`
- `GET /api/v1/alerts/critical`
- `GET /api/v1/alerts/escalated`
- `GET /api/v1/alerts/owned`
- `POST /api/v1/alerts/{id}/acknowledge`
- `POST /api/v1/alerts/{id}/start`
- `POST /api/v1/alerts/{id}/resolve`
- `POST /api/v1/alerts/{id}/suppress`
- `POST /api/v1/alerts/{id}/assign`

#### [MODIFY] [main.py](file:///c:/Users/Aditya/AegisX/backend/src/main.py)
- Include and mount the new alerts router.

---

## Verification Plan

### Automated Tests
Execute integration tests:
```bash
.venv\Scripts\pytest backend/tests/integration/test_alerts.py
```
Execute regression tests:
```bash
.venv\Scripts\pytest
```

We will implement the designated 22 integration tests in `test_alerts.py` to cover alert creation, lifecycle validation, auto-escalation, snapshot dynamic rebuilds, RBAC, scope validation, AI context enrichment, identity preservation after escalation (`test_alert_identity_preserved_after_escalation`), terminal state enforcement (`test_alert_terminal_state_enforcement`), and snapshot consistency (`test_alert_snapshot_rebuild_consistency`).

### Manual Verification
- Verify that standard operators are restricted to alerts for assets within their allowed scopes.
