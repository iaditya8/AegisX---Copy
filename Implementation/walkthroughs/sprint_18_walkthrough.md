# Sprint 18 — Walkthrough

> **Paste your walkthrough for Sprint 18 below this line.**
> Delete this placeholder text when adding your content.

# Sprint 18 Walkthrough: Case Management & Evidence Chain-of-Custody Intelligence

AegisX has been transformed into a comprehensive Case Management & Evidence Intelligence Platform. Complete backward compatibility with all prior sprints has been maintained.

## Changes Made

### Domain Models
- **[NEW] [case.py](file:///c:/Users/Aditya/AegisX/backend/src/domain/entities/case.py)**: Defined `CaseSeverity`, `CaseStatus`, `EvidenceStatus`, `ChainOfCustodyAction` enums and the corresponding Pydantic schemas (`CaseResponse`, `EvidenceResponse`, `ChainOfCustodyEntry`, `CaseHistoryEntry`).

### Core Services
- **[NEW] [case_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/case_service.py)**: Coordinates Case creation, deduplication, state transitions (`OPEN` -> `ACTIVE` -> `UNDER_REVIEW` -> `ESCALATED` -> `RESOLVED` -> `CLOSED`), ownership assignments, and incident evidence sync. Terminal states (`CLOSED`) are fully enforced.
- **[NEW] [case_severity_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/case_severity_registry.py)**: Resolves case severity based on the maximum severity of contained incidents.
- **[NEW] [case_fingerprint_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/case_fingerprint_service.py)**: Calculates stable fingerprints using `SHA256(incident_ids, alert_ids, asset_ids)`.
- **[NEW] [case_history_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/case_history_service.py)**: Manages immutable, append-only case history records.
- **[NEW] [case_snapshot_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/case_snapshot_service.py)**: EPhemeral, rebuildable cache for case metrics.
- **[NEW] [evidence_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/evidence_service.py)**: Handles evidence collection, fingerprinting, preservation rules (immutable fields after collection), verification, and archiving.
- **[NEW] [custody_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/custody_service.py)**: Manages immutable chain-of-custody logs. Enforces that archived evidence cannot be modified, transferred, or recollected.
- **[NEW] [case_evidence_correlation_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/case_evidence_correlation_service.py)**: Dynamically correlates direct case evidence and linked incident evidence.

### Integrations
- **[MODIFY] [worker.py](file:///c:/Users/Aditya/AegisX/backend/src/infrastructure/celery/worker.py)**: Added `CaseService.sync_cases(db)` invocation post-incident synchronization.
- **[MODIFY] [ai_context_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_context_builder.py)**: Injected case metrics, history, evidence, and custody details into prompt contexts.
- **[MODIFY] [ai_prompt_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_prompt_builder.py)**: Updated AI advisory restrictions to explicitly include Case and Evidence mutations, and added `build_case_prompt`.
- **[MODIFY] [main.py](file:///c:/Users/Aditya/AegisX/backend/src/main.py)**: Registered the `cases` router under versioned API routes.

### API Gateway
- **[NEW] [cases.py](file:///c:/Users/Aditya/AegisX/backend/src/api/v1/routers/cases.py)**: Exposed endpoints for case status transitions, evidence collection/transfers, timeline extraction, custody chains, and scoped ownership checks.

## Verification

### Automated Integration Tests
A suite of 34 tests has been implemented in **[test_cases.py](file:///c:/Users/Aditya/AegisX/backend/tests/integration/test_cases.py)** to verify all features:
- Case auto-creation, deduplication, and fingerprint stability.
- State machine terminal state enforcement (`CLOSED`).
- Evidence integrity verification, preservation rules, and fingerprint stability.
- Append-only custody logs, archived terminal enforcement, and post-closure preservation.
- Rebuild consistency for case and evidence snapshots.
- AI Context builder injection.
- RBAC and scope-based ownership checks.

We executed:
```bash
.venv\Scripts\pytest backend/tests/integration/test_cases.py
```
All 34 tests pass successfully.
