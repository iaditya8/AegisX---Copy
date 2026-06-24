# Implementation Plan — Sprint 16: SOC Operations & Alert Management

AegisX will be transformed from a Continuous Monitoring Platform into a SOC Operations Intelligence Platform. Sprint 16 introduces an operational alert management layer that acts upon continuous monitoring events, governance drift events, SLA breaches, and risk acceptance expirations to generate, deduplicate, escalate, and assign alerts to analysts.

## User Review Required

> [!IMPORTANT]
> **Advisory-Only AI**: The AI Security Copilot is strictly advisory. It can explain alert details, reasons, and severities, but is physically blocked from mutating alert states (creating, updating, assigning, closing, or suppressing alerts).
> 
> **In-Memory Operations**: Alert management utilizes in-memory registries and stores to avoid database migrations, mirroring the patterns established in prior sprints (remediations, risk acceptances, and snapshots).
> 
> **Dynamic Rebuild Pattern**: Alert snapshots and statistics are cache-only. If lost, they are fully reconstructed dynamically by traversing past monitoring events and alerts.

## Open Questions

> [!NOTE]
> **Question 1**: Do you approve the default alert severity mappings and escalation aging thresholds (CRITICAL -> 1 day, HIGH -> 3 days, MEDIUM -> 7 days, LOW -> 14 days)?

## Proposed Changes

### [NEW] [alert.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/domain/entities/alert.py)
Domain models and schema definitions for alert modeling:
- Enums: `AlertSeverity` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), `AlertStatus` (`OPEN`, `ACKNOWLEDGED`, `IN_PROGRESS`, `ESCALATED`, `RESOLVED`, `SUPPRESSED`), and `AlertType` (`ASSET_DRIFT`, `FINDING_DRIFT`, `RISK_DRIFT`, `COMPLIANCE_DRIFT`, `RISK_ACCEPTANCE_EXPIRATION`, `SLA_BREACH`, `CRITICAL_FINDING`).
- Schemas: `AlertResponse` containing alert details and state.

### [NEW] [alert_severity_registry.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/alert_severity_registry.py)
- Maps `AlertType` dynamically to their corresponding `AlertSeverity`.

### [NEW] [alert_fingerprint_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/alert_fingerprint_service.py)
- Generates stable, deterministic fingerprints to prevent duplicates: `SHA256(alert_type, asset_id, finding_id, recommendation_id, remediation_id)`.

### [NEW] [alert_generation_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/alert_generation_service.py)
- Consumes monitoring events, governance drift, SLA breaches, and expirations to generate alerts and deduplicate them.
- Emits `alert.created` workflow events and logs audit entries.

### [NEW] [alert_lifecycle_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/alert_lifecycle_service.py)
- Implements alert state machine transitions and enforces terminal status for `RESOLVED` and `SUPPRESSED` (alerts in terminal states cannot be reopened).

### [NEW] [alert_queue_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/alert_queue_service.py)
- Tracks alert assignments, analyst workloads, and aggregates queue stats.

### [NEW] [alert_escalation_registry.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/alert_escalation_registry.py)
- Maps `AlertSeverity` to escalation aging thresholds.

### [NEW] [alert_escalation_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/alert_escalation_service.py)
- Scans open/acknowledged/in-progress alerts, auto-escalates aging alerts based on thresholds, and emits `alert.escalated` workflow events.

### [NEW] [alert_snapshot_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/alert_snapshot_service.py)
- Caches platform-wide status metrics in-memory, supporting dynamic reconstruction from alert history.

### [NEW] [alerts.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/api/v1/routers/alerts.py)
- Exposes REST endpoints for alert management with full RBAC and scope check validations.

### [MODIFY] [main.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/main.py)
- Mount the new alerts router.

### [MODIFY] [worker.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/infrastructure/celery/worker.py)
- At the end of workflow scan steps, invoke `AlertGenerationService.generate_alerts(db)` and `AlertEscalationService.process_escalations(db)` gracefully.

### [MODIFY] [ai_context_builder.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_context_builder.py)
- Inject alert summary details into the prompt context payloads.

### [MODIFY] [ai_prompt_builder.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_prompt_builder.py)
- Embed system constraints on AI advisor-only alert role in prompts.

---

## Verification Plan

### Automated Tests
- Create `backend/tests/integration/test_alerts.py` to verify:
  - Alert creation, state machine transitions, and assignment.
  - Snapshot reconstruction and queue statistics.
  - SLA breach and risk acceptance expiration alert triggers.
  - Copilot advisory prompt enforcements.
  - RBAC permission boundaries and scope boundaries.
  - Fingerprint deduplication and terminal state rules.
- Execute integration tests:
  ```powershell
  .venv\Scripts\pytest backend/tests/integration/test_alerts.py
  ```
- Formatting & Linting checks:
  ```powershell
  .venv\Scripts\ruff check backend/
  .venv\Scripts\black --check backend/
  ```

### Manual Verification
- None required; verified entirely via integration tests.
