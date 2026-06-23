# Sprint 17 — Walkthrough

> **Paste your walkthrough for Sprint 17 below this line.**
> Delete this placeholder text when adding your content.

# Sprint 17 Walkthrough: Incident Management & Investigation Workflows

We have successfully implemented Sprint 17, transforming AegisX into an **Incident Management & Investigation Workflow Platform**. All requirements and hardening rules have been met, verified with 16 new integration tests, and validated against the entire regression test suite (316 tests passing in total).

## Completed Changes

### 1. Domain Models
* [incident.py](file:///c:/Users/Aditya/AegisX/backend/src/domain/entities/incident.py): Created structured models (`IncidentSeverity`, `IncidentStatus`, `InvestigationStatus`, `IncidentResponse`, `InvestigationEntry`, `IncidentHistoryEntry`) aligning with in-memory stores.

### 2. Registries & Fingerprinting
* [incident_severity_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/incident_severity_registry.py): Maps linked alert severity combinations to incident severity level deterministically.
* [incident_fingerprint_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/incident_fingerprint_service.py): Generates stable SHA-256 fingerprints based on sorted list of `alert_ids`, `asset_ids`, and `finding_ids`.

### 3. Core Services
* [incident_history_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/incident_history_service.py): Enforces **Incident History Preservation Rule** (immutable logs, append-only entries, surviving resets/closure/snapshot rebuilds).
* [incident_evidence_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/incident_evidence_service.py): Enforces **Incident Evidence Stability Rule** (immutable read-only snapshots of linked entities, marked historical if deleted or changed state, surviving incident closure).
* [incident_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/incident_service.py): Orchestrates workflow transitions and groups active alerts by asset. Enforces **Closed Incident Enforcement** (CLOSED is terminal and cannot be reopened/mutated) and **Incident Synchronization Rule** (deduplication of incident creation on identical fingerprint).
* [investigation_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/investigation_service.py): Supports analyst note tracking and timeline logging.
* [incident_escalation_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/incident_escalation_service.py): Implements manual team/owner/management escalations and worker-driven automatic aging escalations.
* [incident_snapshot_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/incident_snapshot_service.py): Caches incident statistics. Enforces **Incident Snapshot Consistency** (rebuilds cache dynamically from active incidents if lost/corrupted).

### 4. Integrations
* [worker.py](file:///c:/Users/Aditya/AegisX/backend/src/infrastructure/celery/worker.py): Injects incident synchronization and auto-escalation check blocks at the end of the celery workflow run.
* [ai_context_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_context_builder.py): Injects `incident_summary`, `incident_status`, `incident_owner`, `incident_timeline`, and `linked_evidence` into AI context prompts, and exposes `build_incident_context`.
* [ai_prompt_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_prompt_builder.py): Embeds prompt constraints stating the AI Security Copilot's advisor-only role physically blocking it from mutating incidents or investigations.

### 5. API Gateway
* [incidents.py](file:///c:/Users/Aditya/AegisX/backend/src/api/v1/routers/incidents.py): Exposes REST endpoints with RBAC (operator/admin required for mutations, reader role restricted to read-only retrieval) and scope checks limiting operator access to incidents containing owned assets:
  * `GET /api/v1/incidents`
  * `GET /api/v1/incidents/{id}`
  * `GET /api/v1/incidents/open`
  * `GET /api/v1/incidents/escalated`
  * `GET /api/v1/incidents/critical`
  * `POST /api/v1/incidents/{id}/assign`
  * `POST /api/v1/incidents/{id}/triage`
  * `POST /api/v1/incidents/{id}/start`
  * `POST /api/v1/incidents/{id}/contain`
  * `POST /api/v1/incidents/{id}/resolve`
  * `POST /api/v1/incidents/{id}/close`
  * `GET /api/v1/incidents/{id}/timeline`
  * `GET /api/v1/incidents/{id}/evidence`
  * `POST /api/v1/incidents/{id}/notes`
  * `POST /api/v1/incidents/{id}/escalate/team`
  * `POST /api/v1/incidents/{id}/escalate/owner`
  * `POST /api/v1/incidents/{id}/escalate/management`
* [main.py](file:///c:/Users/Aditya/AegisX/backend/src/main.py): Mounts and registers the incidents router.

## Verification & Testing

### Automated Test Execution
Run the specific incident integration tests:
```bash
.venv\Scripts\pytest backend/tests/integration/test_incidents.py
```
Run the full regression test suite:
```bash
.venv\Scripts\pytest
```

All **316 tests passed successfully** (including new ones verifying history preservation, evidence stability, terminal state limits, escalation/synchronization stability), validating backward compatibility and style compliance (`ruff` check passed).
