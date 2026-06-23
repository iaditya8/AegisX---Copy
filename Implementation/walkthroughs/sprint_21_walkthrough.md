# Sprint 21 — Walkthrough

> **Paste your walkthrough for Sprint 21 below this line.**
> Delete this placeholder text when adding your content.

# Walkthrough: Sprint 21 – Threat Hunting Intelligence

AegisX has been successfully upgraded into a Threat Hunting Intelligence Platform. This sprint introduces Hunt Management, Hunt Hypotheses, ATT&CK-driven Hunting, IOC-driven Hunting, Hunt Findings, Hunt Coverage Analytics, Hunt Drift Detection, and Hunt Intelligence Snapshots. Full backward compatibility with Sprints 1–20 is preserved.

## Changes Completed

### Domain Models & Registries
- [NEW] [hunt.py](file:///c:/Users/Aditya/AegisX/backend/src/domain/entities/hunt.py): Defines enums `HuntSeverity`, `HuntStatus`, and `HuntType`, alongside response schemas `HuntResponse`, `HuntHypothesisResponse`, `HuntFindingResponse`, and `HuntHistoryEntry`.
- [NEW] [hunt_type_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_type_registry.py): Provides type-based validation and registry for hunt typologies.
- [NEW] [hunt_severity_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_severity_registry.py): Manages severity level resolution and highest-level resolution across multiple tags.

### Core Services
- [NEW] [hunt_fingerprint_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_fingerprint_service.py): Generates stable `SHA256` fingerprints using hunt type, normalized title, and sorted related entities.
- [NEW] [hunt_history_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_history_service.py): Maintains immutable append-only historical audit trails for hunt operations.
- [NEW] [hunt_hypothesis_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_hypothesis_service.py): Handles hypothesis creation, storage, and validation for active hunts.
- [NEW] [hunt_finding_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_finding_service.py): Manages hunt findings and correlates them to other entities (Assets, Findings, Alerts, Incidents, Cases, Detections, IOCs).
- [NEW] [hunt_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_service.py): Orchestrates hunt lifecycle management, sync runs, and ownership assignment while enforcing terminal state constraints.
- [NEW] [ioc_hunt_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ioc_hunt_service.py): Triggers threat hunts automatically from IOC drifts, reputation spikes, and new correlations.
- [NEW] [attack_hunt_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/attack_hunt_service.py): Automatically schedules threat hunts for ATT&CK detection coverage gaps.
- [NEW] [hunt_coverage_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_coverage_service.py): Computes coverage analytics metrics for ATT&CK techniques, campaigns, actors, and IOCs.
- [NEW] [hunt_drift_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_drift_service.py): Emits workflow events (`hunt.drift`, `hunt.coverage_changed`) for status, completion, and coverage modifications.
- [NEW] [hunt_snapshot_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_snapshot_service.py): Cache-only, rebuildable threat hunting metrics snapshot dashboard.

### Integrations
- [MODIFY] [worker.py](file:///c:/Users/Aditya/AegisX/backend/src/infrastructure/celery/worker.py): Injects threat hunting generation, drift engine processing, and snapshot updates into the Celery task execution chain.
- [MODIFY] [ai_context_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_context_builder.py): Injects threat hunting summary block (active hunts, hypotheses, coverage stats, and findings) into all context profiles.
- [MODIFY] [ai_prompt_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_prompt_builder.py): Restricts AI from making mutations on threat hunting properties.

### API Gateway
- [NEW] [hunts.py](file:///c:/Users/Aditya/AegisX/backend/src/api/v1/routers/hunts.py): Exposes REST endpoints (`/api/v1/hunts`, `/hunts/active`, `/hunts/{id}/activate`, etc.) with standard response validation and role-based access control (RBAC).
- [MODIFY] [main.py](file:///c:/Users/Aditya/AegisX/backend/src/main.py): Registers the new `/api/v1/hunts` router.

---

## Validation & Testing Results

### Automated Tests
Successfully ran the threat hunting integration test suite using:
`.venv\Scripts\pytest backend/tests/integration/test_hunts.py`

Result:
```
======================= 58 passed, 3 warnings in 0.20s ========================
```

Successfully executed the complete regression suite to confirm zero regressions across all modules (Sprints 1–21):
`.venv\Scripts\pytest`

Result:
```
====================== 479 passed, 12 warnings in 12.83s ======================
```

### Verification Checks

| Requirement / Rule | Verification Status | Details |
| --- | --- | --- |
| **Threat Hunt Source Rule** | ✅ Confirmed | All hunts are registry-driven and use AegisX in-memory datasets; no external query integrations are executed. |
| **Hunt Identity Preservation Rule** | ✅ Confirmed | Sync preserves `hunt_id`, ownership, hypotheses, findings, history, timestamps, and escalation history on matching fingerprints. |
| **Hunt Terminal State Rule** | ✅ Confirmed | `CLOSED` status is terminal and non-reversible. |
| **Hunt History Preservation Rule** | ✅ Confirmed | Immutable history appends new events copy-safe without modifying existing entries. |
| **Hypothesis & Finding Stability** | ✅ Confirmed | Hypotheses and findings remain attached to their respective hunts across status changes, synchronization, and drift processing. |
| **Drift & Coverage Calculations** | ✅ Confirmed | Correctly calculates coverage for attack, actor, campaign, and IOC matrices, and triggers drift alerts on changes. |
| **AI Advisor Enforcement** | ✅ Confirmed | AI prompt builder rules physically block AI Security Copilot from executing mutations on hunts. |
| **Scope & RBAC Validation** | ✅ Confirmed | API endpoints enforce scope-ownership checks and validate role-based access permissions. |

---

## Backward Compatibility Statement
All Sprint 21 schemas, models, and endpoints maintain full backward compatibility with Sprints 1–20. There are zero database schema alterations or migrations required, as state remains registry-driven and in-memory.
