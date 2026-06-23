# Sprint 26 — Implementation Plan

> **Paste your implementation plan for Sprint 26 below this line.**
> Delete this placeholder text when adding your content.

# Sprint 26: Security Program Intelligence

This sprint introduces the **Security Program Intelligence Platform** to AegisX. It expands the platform from Security Effectiveness Intelligence (Sprint 25) to full Security Program Management, providing executive stakeholders with deterministic, auditable, and snapshot-rebuildable metrics on organizational health, objectives, initiatives, KPIs, and KRIs.

## Architectural Constraints (Sprint 1–25 Compliance)
- Registry-driven design
- Deterministic fingerprinting (`SHA256` hashing)
- Identity preservation
- Terminal-state enforcement (e.g., `CLOSED` or `COMPLETED` cannot be reactivated)
- Immutable historical records
- Snapshot rebuild consistency
- In-memory storage only (No DB migrations)
- No external integrations
- No breaking API changes
- Full backward compatibility
- AI Advisory-only enforcement

## Domain Models (`backend/src/domain/entities/security_program.py`)

I will create a unified domain file for Security Program entities containing the required models:

1. **`ProgramSeverity` (Enum)**
2. **`ProgramStatus` (Enum):** `PLANNED`, `ACTIVE`, `UNDER_REVIEW`, `COMPLETED`, `CLOSED`
3. **`KPIStatus` (Enum):** `ON_TARGET`, `AT_RISK`, `OFF_TARGET`
4. **`KRIStatus` (Enum):** `LOW_RISK`, `MEDIUM_RISK`, `HIGH_RISK`, `CRITICAL_RISK`
5. **`SecurityProgramResponse` (BaseModel)**
6. **`ProgramObjectiveResponse` (BaseModel)**
7. **`ProgramInitiativeResponse` (BaseModel)**
8. **`KPIResponse` (BaseModel)**
9. **`KRIResponse` (BaseModel)**
10. **`ProgramHistoryEntry` (BaseModel)**

## Proposed Registries (`backend/src/services/`)

1. **`security_program_registry.py`**:
   - Maintains supported program categories and validates program classifications.
2. **`kpi_registry.py`**:
   - Pre-seeded with: Mean Time To Detect, Mean Time To Respond, Critical Exposure Count, Control Effectiveness Score, Detection Coverage Score, Threat Hunt Coverage.
3. **`kri_registry.py`**:
   - Pre-seeded with: Critical Risk Growth, Open Incident Growth, Exposure Growth, Detection Regression, Threat Coverage Regression.

## Proposed Services (`backend/src/services/`)

To adhere to the Single Responsibility Principle and existing patterns, I will implement the following services:

1. **`security_program_service.py`**: Manages the core lifecycle, identity preservation, fingerprinting, and state transitions of `SecurityProgram`s.
   > **Security Program Terminal State Rule**
   > `COMPLETED` and `CLOSED` are terminal states.
   > Requirements:
   > - synchronization cannot reactivate COMPLETED/CLOSED programs
   > - worker refresh cycles cannot reactivate COMPLETED/CLOSED programs
   > - KPI recalculations cannot reactivate COMPLETED/CLOSED programs
   > - KRI recalculations cannot reactivate COMPLETED/CLOSED programs
   > - drift processing cannot reactivate COMPLETED/CLOSED programs
   > - snapshot rebuilds cannot reactivate COMPLETED/CLOSED programs
   > 
   > A new Security Program may only be created if the fingerprint changes.
2. **`program_history_service.py`**: Ensures immutable audit trails (`ProgramHistoryEntry`) of program state changes.
3. **`kpi_service.py`**: Calculates KPI values based on the `kpi_registry.py`.
4. **`kri_service.py`**: Calculates KRI values based on the `kri_registry.py`.
5. **`program_health_service.py`**: Deterministically calculates the full program health engine, including: `program_score`, `objective_completion`, `initiative_completion`, `KPI performance`, and `KRI exposure`.
6. **`program_correlation_service.py`**: Manages correlations between programs and existing intelligence securely and immutably.
7. **`program_drift_service.py`**: Detects when KPI performance, KRI exposure, or program health drifts across thresholds.
8. **`security_program_snapshot_service.py`**: Provides executive summaries and handles dynamic cache rebuilding if caches are corrupted/deleted.
9. **`program_fingerprint_service.py`**: Manages deterministic fingerprinting for identity preservation.

## Integrations

1. **`backend/src/infrastructure/celery/worker.py`**: Hook the following into the continuous refresh cycle:
   - `SecurityProgramService.sync_programs()`
   - `KPIService.calculate()`
   - `KRIService.calculate()`
   - `ProgramHealthService.calculate()`
   - `ProgramDriftService.process_drift()`
   - `SecurityProgramSnapshotService.generate_snapshot()`
2. **`backend/src/services/ai_context_builder.py`**: Inject Security Program intelligence into the context.
3. **`backend/src/services/ai_prompt_builder.py`**: Update prompt rules to enforce the AI as an advisor for program metrics.
4. **`backend/src/api/v1/routers/security_program.py`**: Add REST endpoints for program intelligence.
5. **`backend/src/main.py`**: Register the `security_program.py` router.

## Verification Plan

Create `backend/tests/integration/test_security_program.py` to ensure all workflows and edge cases are validated.

**85+ Total Integration Tests**
The test suite will contain a minimum of 85 integration tests, with explicit comprehensive coverage for:
- objective completion
- initiative completion
- KPI thresholds
- KRI thresholds
- duplicate prevention
- drift persistence
- correlation persistence
- worker refresh cycles
- terminal-state enforcement
- snapshot rebuilds
- advisory-only enforcement

**Mandatory Subset Required (50 Tests):**
1. `test_program_auto_creation()`
2. `test_program_fingerprint_stability()`
3. `test_program_activate_transition()`
4. `test_program_review_transition()`
5. `test_program_complete_transition()`
6. `test_program_close_transition()`
7. `test_program_identity_preserved_after_completion()`
8. `test_program_identity_preserved_after_closure()`
9. `test_ai_context_program_injection()`
10. `test_rbac_program_scope_validation()`
11. `test_program_terminal_state_not_reactivated_by_sync()`
12. `test_snapshot_rebuild_consistency()`
13. `test_snapshot_rebuild_after_cache_deletion()`
14. `test_snapshot_rebuild_after_cache_corruption()`
15. `test_program_duplicate_prevention()`
16. `test_program_history_preserved()`
17. `test_program_correlation_preservation()`
18. `test_kpi_calculation()`
19. `test_kri_calculation()`
20. `test_program_health_score()`
21. `test_program_score_stability()`
22. `test_program_score_change_detection()`
23. `test_objective_completion()`
24. `test_initiative_completion()`
25. `test_kpi_drift_detection()`
26. `test_kri_drift_detection()`
27. `test_ai_advisory_only_enforcement()`
28. `test_program_sync_preserves_identity()`
29. `test_kpi_registry_validation()`
30. `test_kri_registry_validation()`
31. `test_worker_integration()`
32. `test_completed_program_not_reactivated_by_worker()`
33. `test_closed_program_not_reactivated_by_worker()`
34. `test_completed_program_not_reactivated_by_snapshot()`
35. `test_closed_program_not_reactivated_by_snapshot()`
36. `test_completed_program_not_reactivated_by_drift()`
37. `test_closed_program_not_reactivated_by_drift()`
38. `test_completed_program_not_reactivated_by_kpi_refresh()`
39. `test_closed_program_not_reactivated_by_kpi_refresh()`
40. `test_completed_program_not_reactivated_by_kri_refresh()`
41. `test_closed_program_not_reactivated_by_kri_refresh()`
42. `test_program_history_immutable()`
43. `test_program_history_survives_snapshot_rebuild()`
44. `test_program_correlation_append_only()`
45. `test_program_health_score_deterministic()`
46. `test_program_snapshot_not_authoritative()`
47. `test_program_snapshot_rebuild_from_source_of_truth()`
48. `test_program_identity_preserved_after_health_recalculation()`
49. `test_program_identity_preserved_after_kpi_refresh()`
50. `test_program_identity_preserved_after_kri_refresh()`
