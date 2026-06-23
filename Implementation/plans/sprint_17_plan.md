# Sprint 17 — Implementation Plan

> **Paste your implementation plan for Sprint 17 below this line.**
> Delete this placeholder text when adding your content.

# Sprint 17 Implementation Plan: Incident Management & Investigation Workflows

AegisX will be transformed from a SOC Operations Platform into an Incident Management & Investigation Workflow Platform. Sprint 17 introduces structured incidents, deterministic tracking, analyst-driven investigation workflows, timeline auditing, evidence correlation, and advisor-only AI context builder integration.

## User Review Required

> [!IMPORTANT]
> **Advisory-Only AI**: The AI Security Copilot remains strictly advisory. It can explain incidents, summarize investigations, and explain evidence, but is physically blocked from mutating incident states (creating, updating, assigning, closing, or approving investigations).
> 
> **In-Memory Operations**: Incident and investigation management utilizes in-memory registries and stores to avoid database migrations, mirroring the patterns established in prior sprints (remediations, alerts, and snapshots).
> 
> **Scope Filtering & RBAC**: Standard operators are restricted to incidents where all linked assets are within their allowed scopes. Incident mutations will require the `operator` or `admin` role, and standard `reader` roles will be limited to read-only retrieval.

## Proposed Changes

### Domain Models

#### [NEW] [incident.py](file:///c:/Users/Aditya/AegisX/backend/src/domain/entities/incident.py)
Create domain definitions for incident modeling:
- `IncidentSeverity(str, Enum)`: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- `IncidentStatus(str, Enum)`: `OPEN`, `TRIAGED`, `INVESTIGATING`, `ESCALATED`, `CONTAINED`, `RESOLVED`, `CLOSED`
- `InvestigationStatus(str, Enum)`: `OPEN`, `ACTIVE`, `COMPLETED`
- `IncidentResponse`: Pydantic model containing `incident_id`, `incident_fingerprint`, `title`, `description`, `severity`, `status`, `owner`, `created_at`, `updated_at`, `alert_ids`, `asset_ids`, `finding_ids`, `recommendation_ids`, `remediation_ids`.
- `InvestigationEntry`: Pydantic model containing `entry_id`, `incident_id`, `timestamp`, `analyst`, `action`, `notes`.
- `IncidentHistoryEntry`: Pydantic model containing `incident_id`, `timestamp`, `event_type`, `details`.

---

### Registries & Fingerprinting

#### [NEW] [incident_severity_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/incident_severity_registry.py)
- Maps alert severity combinations to incident severity deterministically:
  - If any alert is `CRITICAL` -> incident severity is `CRITICAL`.
  - If multiple `HIGH` alerts -> incident severity is `HIGH`.
  - If multiple `MEDIUM` alerts -> incident severity is `MEDIUM`.
  - Fallback/Otherwise -> `LOW` or `MEDIUM` based on count.

#### [NEW] [incident_fingerprint_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/incident_fingerprint_service.py)
- Generates stable, deterministic fingerprints:
  `SHA256(alert_ids, asset_ids, finding_ids)`
- Ensures the fingerprint remains stable across ownership changes, escalation, status transitions, investigation updates, containment, and closure.
- Fingerprint only changes when linked alerts, findings, or assets change.

---

### Core Services

#### [NEW] [incident_history_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/incident_history_service.py)
- Keeps track of all state transitions and logs historical records: `CREATED`, `ASSIGNED`, `TRIAGED`, `INVESTIGATION_STARTED`, `INVESTIGATION_UPDATED`, `ESCALATED`, `CONTAINED`, `RESOLVED`, `CLOSED`.
- **Incident History Preservation Rule**: Incident history entries are immutable. Existing history records must never be modified or deleted. New lifecycle actions, escalations, investigation updates, containment, resolution, and closure must append new records. History entries must survive synchronization events, ownership changes, escalation events, closure, and snapshot rebuilds. History is the authoritative audit trail and must never be reconstructed from incident state.

#### [NEW] [incident_evidence_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/incident_evidence_service.py)
- Correlates read-only evidence dynamically: lists linked alerts, assets, findings, recommendations, remediations, governance events, and monitoring events.
- **Incident Evidence Stability Rule**: Evidence references are immutable historical references. Linked evidence must never be modified in-place. Evidence records are read-only references. If a linked entity changes state, preserve the original evidence reference and do not remove historical references. If an entity is deleted or no longer active, the evidence reference remains visible and is marked as historical. Investigation timelines must continue referencing historical evidence even after incident closure.

#### [NEW] [incident_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/incident_service.py)
- Core workflow transitions and incident store. Implements the designated incident state machine:
  - `OPEN` -> `TRIAGED`
  - `TRIAGED` -> `INVESTIGATING` or `ESCALATED`
  - `INVESTIGATING` -> `CONTAINED` or `ESCALATED`
  - `ESCALATED` -> `INVESTIGATING` or `CONTAINED`
  - `CONTAINED` -> `RESOLVED`
  - `RESOLVED` -> `CLOSED`
  - `CLOSED` -> terminal state (no transitions allowed). Enforce Closed Incident Enforcement where CLOSED is terminal and incidents in CLOSED state cannot be reopened or mutated.
- Synchronizes qualifying alerts into unified asset-grouped incidents.
  - Incident Synchronization Rule: If alert processing is rerun and generates the same incident fingerprint: Do not create a new incident. Preserve incident_id, ownership, investigation history, incident history, escalation history, timestamps, and evidence references. Only update mutable metadata when required.
- Emits workflow events and logs to `AuditService`.

#### [NEW] [investigation_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/investigation_service.py)
- Supports adding analyst notes, findings, starting and completing investigations.
- Ensures all activities write to `InvestigationEntry` and `IncidentHistoryEntry` timeline structures.

#### [NEW] [incident_escalation_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/incident_escalation_service.py)
- Supports manual and worker-driven escalations (`escalate_to_team`, `escalate_to_owner`, `escalate_to_management`). Emits `incident.escalated` workflow events.

#### [NEW] [incident_snapshot_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/incident_snapshot_service.py)
- Memory-cached incident statistics. 
- Incident Snapshot Consistency: Snapshots must never be treated as the source of truth. Must derive all statistics from active incident records. If the cache is cleared, lost, corrupted, or deleted, `get_snapshot()` and `generate_snapshot()` must rebuild dynamically from incident service records.

---

### Integrations

#### [MODIFY] [worker.py](file:///c:/Users/Aditya/AegisX/backend/src/infrastructure/celery/worker.py)
- In workflow scan completion step, invoke `IncidentService.sync_alerts(db)` and `IncidentEscalationService.process_escalations(db)` gracefully wrapped in exception handling blocks.

#### [MODIFY] [ai_context_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_context_builder.py)
- Inject `incident_summary`, `incident_status`, `incident_owner`, `incident_timeline`, and `linked_evidence` into prompt contexts.

#### [MODIFY] [ai_prompt_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_prompt_builder.py)
- Embed advisor-only constraints restricting the AI Security Copilot from performing mutating actions on incidents.

---

### API Gateway

#### [NEW] [incidents.py](file:///c:/Users/Aditya/AegisX/backend/src/api/v1/routers/incidents.py)
Exposes REST endpoints:
- `GET /api/v1/incidents`
- `GET /api/v1/incidents/{id}`
- `GET /api/v1/incidents/open`
- `GET /api/v1/incidents/escalated`
- `GET /api/v1/incidents/critical`
- `POST /api/v1/incidents/{id}/assign`
- `POST /api/v1/incidents/{id}/triage`
- `POST /api/v1/incidents/{id}/start`
- `POST /api/v1/incidents/{id}/contain`
- `POST /api/v1/incidents/{id}/resolve`
- `POST /api/v1/incidents/{id}/close`
- `GET /api/v1/incidents/{id}/timeline`
- `GET /api/v1/incidents/{id}/evidence`

#### [MODIFY] [main.py](file:///c:/Users/Aditya/AegisX/backend/src/main.py)
- Include and mount the new incidents router.

---

## Verification Plan

### Automated Tests
Execute integration tests:
```bash
.venv\Scripts\pytest backend/tests/integration/test_incidents.py
```
- Includes the test: `test_incident_identity_preserved_after_escalation` to ensure fingerprint is unchanged, incident_id is unchanged, history is preserved, and state transitions to ESCALATED correctly without duplication.
- Includes the test: `test_incident_evidence_preserved_after_closure` to verify that after an incident is resolved and closed, evidence references are still available, the timeline still references evidence, and no evidence corruption occurs.
- Includes the test: `test_incident_history_preserved_after_closure` to verify that after going through the full lifecycle (create, assign, start, escalate, resolve, close), the history count is unchanged, entries and order are preserved, closure is appended, and no records are removed.
Execute regression tests:
```bash
.venv\Scripts\pytest
```

We will implement 24+ integration tests in `test_incidents.py` covering creation, deduplication, identity preservation, fingerprint stability, state machine rules, assignment, escalation, investigation timeline, evidence linking, snapshots, RBAC, scope ownership, and AI context builder integration. We will maintain code coverage `>= 85%`.

### Manual Verification
- Verify that standard operators are restricted from retrieving or mutating incidents involving assets outside their allowed scopes.
