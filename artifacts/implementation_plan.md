# Implementation Plan — Sprint 17: Incident Management & Investigation Workflows

AegisX will be transformed from a SOC Operations Platform into an Incident Management & Investigation Workflow Platform. Sprint 17 introduces structured incidents, deterministic tracking, analyst-driven investigation workflows, timeline auditing, evidence correlation, and advisor-only AI context builder integration.

## User Review Required

> [!IMPORTANT]
> **Advisory-Only AI**: The AI Security Copilot remains strictly advisory. It can explain incidents, summarize investigations, and explain evidence, but is physically blocked from mutating incident states (creating, updating, assigning, closing, or approving investigations).
> 
> **In-Memory Operations**: Incident and investigation management utilizes in-memory registries and stores to avoid database migrations, mirroring the patterns established in prior sprints (remediations, alerts, and snapshots).
> 
> **Scope Filtering & RBAC**: Standard operators are restricted to incidents where all linked assets are within their allowed scopes. Incident mutations will require the `operator` or `admin` role, and standard `reader` roles will be limited to read-only retrieval.
> 
> **Closed Incident Enforcement**: The `CLOSED` state is strictly terminal. Once closed, an incident cannot be reopened, updated, or otherwise mutated.

## Open Questions

- None. (Question 1 resolved: Approved default incident severity mapping rule.)

## Proposed Changes

### [NEW] [incident.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/domain/entities/incident.py)
Domain models and schema definitions for incident and investigation tracking:
- Enums: `IncidentSeverity` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), `IncidentStatus` (`OPEN`, `TRIAGED`, `INVESTIGATING`, `ESCALATED`, `CONTAINED`, `RESOLVED`, `CLOSED`), and `InvestigationStatus` (`OPEN`, `ACTIVE`, `COMPLETED`).
- Schemas: `IncidentResponse`, `InvestigationEntry`, and `IncidentHistoryEntry` Pydantic models.

### [NEW] [incident_severity_registry.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/incident_severity_registry.py)
- Maps alert severity combinations to incident severity level deterministically (e.g., if any alert is CRITICAL -> incident is CRITICAL).

### [NEW] [incident_fingerprint_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/incident_fingerprint_service.py)
- Generates stable, deterministic fingerprints to prevent duplicate incidents: `SHA256(alert_ids, asset_ids, finding_ids)`. Fingerprints survive transitions and ownership changes.

### [NEW] [incident_history_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/incident_history_service.py)
- Tracks state transitions and appends immutable history records that persist across synchronization and snapshot rebuilds.

### [NEW] [incident_evidence_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/incident_evidence_service.py)
- Correlates read-only evidence references (alerts, assets, findings, recommendations, remediations) dynamically, ensuring they survive incident closure.

### [NEW] [incident_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/incident_service.py)
- Manages the core incident state machine (OPEN -> TRIAGED -> INVESTIGATING -> CONTAINED -> RESOLVED -> CLOSED) and synchronizes/deduplicates alerts into unified incidents. Enforces Closed Incident rule and emits workflow events.

### [NEW] [investigation_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/investigation_service.py)
- Supports starting/completing investigations, tracking analyst notes, and writing to timeline structures.

### [NEW] [incident_escalation_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/incident_escalation_service.py)
- Implements manual escalations (to team, owner, or management) and emits `incident.escalated` workflow events.

### [NEW] [incident_snapshot_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/incident_snapshot_service.py)
- Caches incident statistics in-memory and supports dynamic reconstruction from incident service records if lost or cleared.

### [NEW] [incidents.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/api/v1/routers/incidents.py)
- Exposes REST endpoints for incident management, timeline retrieving, and evidence list. Includes RBAC and operator scope constraints.

### [MODIFY] [main.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/main.py)
- Mount the new incidents router.

### [MODIFY] [worker.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/infrastructure/celery/worker.py)
- Stages alert synchronization `IncidentService.sync_alerts(db)` and `IncidentEscalationService.process_escalations(db)` at the end of scan tasks.

### [MODIFY] [ai_context_builder.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_context_builder.py)
- Inject incident context attributes (summary, status, owner, timeline, evidence) into context builder prompts.

### [MODIFY] [ai_prompt_builder.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_prompt_builder.py)
- Enforce advisor-only incident constraints to block the AI Security Copilot from performing mutations on incidents.

---

## Verification Plan

### Automated Tests
- Create `backend/tests/integration/test_incidents.py` to verify:
  - Incident creation, fingerprinting stability, state transitions, and assignment.
  - Snapshot reconstruction and timeline retrieves.
  - History preservation and evidence visibility after incident closure.
  - Copilot advisory prompt enforcements.
  - RBAC boundaries and operator scope boundaries.
- Execute integration tests:
  ```powershell
  .venv\Scripts\pytest backend/tests/integration/test_incidents.py
  ```
- Execute regression tests:
  ```powershell
  .venv\Scripts\pytest
  ```
- Formatting & Linting checks:
  ```powershell
  .venv\Scripts\ruff check backend/
  .venv\Scripts\black --check backend/
  ```

### Manual Verification
- Verify that standard operators are restricted from retrieving or mutating incidents involving assets outside their allowed scopes.
