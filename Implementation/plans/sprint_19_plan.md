# Sprint 19 — Implementation Plan

> **Paste your implementation plan for Sprint 19 below this line.**
> Delete this placeholder text when adding your content.

# Sprint 19 Implementation Plan: Detection Engineering Intelligence

AegisX will be transformed from a Case Management & Evidence Intelligence Platform into a Detection Engineering Intelligence Platform. Sprint 19 introduces detection rule management, detection coverage analysis, MITRE ATT&CK mapping, gap detection, detection drift tracking, and coverage snapshots.

## User Review Required

> [!IMPORTANT]
> **Advisory-Only AI**: The AI Security Copilot remains strictly advisory. It can explain rules, summarize gaps, and verify mappings but is physically blocked from mutating detection rules (creating, modifying, disabling, or mapping techniques).
> 
> **In-Memory Operations**: Detections, coverage scores, and ATT&CK mappings are stored in-memory, avoiding database migrations and preserving compatibility.
> 
> **Scope Filtering & RBAC**: Detections are scoped. Operators and Readers are restricted to detections within scopes they own. Mutations (POST/actions) require the `admin` or `operator` role.

## Proposed Changes

### Domain Models

#### [NEW] [detection.py](file:///c:/Users/Aditya/AegisX/backend/src/domain/entities/detection.py)
Create domain definitions for detection modeling:
- `DetectionSeverity(str, Enum)`: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- `DetectionStatus(str, Enum)`: `ACTIVE`, `DISABLED`, `DEPRECATED`
- `CoverageStatus(str, Enum)`: `COVERED`, `PARTIALLY_COVERED`, `NOT_COVERED`
- `DetectionResponse`: Pydantic model containing `detection_id`, `detection_fingerprint`, `name`, `description`, `severity`, `status`, `attack_techniques`, `created_at`, `updated_at`, `scope_id`.
- `DetectionCoverageResponse`: Pydantic model containing `technique_id`, `coverage_status`, `detection_count`, `coverage_score`.

---

### Registries & Fingerprinting

#### [NEW] [attack_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/attack_registry.py)
- In-memory registry containing pre-seeded MITRE ATT&CK techniques:
  - `T1059` (Command and Scripting Interpreter)
  - `T1562` (Impair Defenses)
  - `T1078` (Valid Accounts)
  - `T1027` (Obfuscated Files)
  - `T1105` (Ingress Tool Transfer)
  - `T1047` (WMI)
  - `T1055` (Process Injection)

#### [NEW] [detection_severity_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/detection_severity_registry.py)
- Resolves and maps detection severities to avoid hardcoded logic elsewhere.

#### [NEW] [detection_fingerprint_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/detection_fingerprint_service.py)
- Generates stable, deterministic fingerprints: `SHA256(detection_name, sorted_attack_techniques)`.
- **Detection Fingerprint Stability Rule**: Fingerprint remains stable across owner changes, status transitions, coverage recalculations, and snapshot rebuilds. It only changes when `name` or `attack_techniques` change.

---

### Core Services

#### [NEW] [detection_history_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/detection_history_service.py)
- Records immutable, append-only history entries for: `CREATED`, `UPDATED`, `DISABLED`, `DEPRECATED`, `ATTACK_MAPPING_CHANGED`.

#### [NEW] [detection_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/detection_service.py)
- Coordinates detection creation, updates, and disabling/deprecation.
- **Detection Synchronization Rule**: If synchronization is rerun and produces the same fingerprint, preserve `detection_id`, fingerprint, history, and creation timestamp. Only update mutable metadata.
- **Detection Terminal State Rule**: `DISABLED` and `DEPRECATED` are terminal states. A detection in a terminal state cannot be automatically reactivated. Coverage recalculations, snapshot rebuilds, and synchronization runs producing the same fingerprint must not reactivate terminal detections. A new detection may only be created if the fingerprint, ATT&CK mapping, or name changes.

#### [NEW] [detection_coverage_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/detection_coverage_service.py)
- Evaluates coverage:
  - `COVERED`: Technique mapped to one or more `ACTIVE` detections.
  - `PARTIALLY_COVERED`: Mapped to detections, but all are `DISABLED` or `DEPRECATED`.
  - `NOT_COVERED`: Not mapped to any detections.
- Coverage score: `covered techniques / total registered techniques`.
- **ATT&CK Mapping Preservation Rule**: Mapped ATT&CK relationships are historical intelligence records. Mapping changes append history, and existing mappings are never deleted from history. Coverage calculations use current mappings. Historical reports and drift analysis can reconstruct and compare previous vs current mappings.

#### [NEW] [detection_gap_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/detection_gap_service.py)
- Analyzes coverage gaps, regressions, and drifts. Emits `detection.gap_detected` and `detection.coverage_regressed` events.

#### [NEW] [detection_drift_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/detection_drift_service.py)
- Identifies coverage score decreases or mappings changing. Emits `detection.drift` events.

#### [NEW] [detection_snapshot_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/detection_snapshot_service.py)
- **Detection Snapshot Consistency**: Detection snapshots are cache-only structures. They must never be treated as the source of truth, and all snapshot metrics must derive from active detection records. If missing, corrupted, or deleted, `generate_snapshot()` and `get_snapshot()` must rebuild dynamically from active detection records, ensuring no state exists exclusively inside caches.

---

### Integrations

#### [MODIFY] [worker.py](file:///c:/Users/Aditya/AegisX/backend/src/infrastructure/celery/worker.py)
- Invokes coverage, gap, and drift service checks gracefully on scan workflow completion.

#### [MODIFY] [ai_context_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_context_builder.py)
- Inject `detection_summary`, `coverage_score`, `covered_techniques`, `uncovered_techniques`, and `coverage_gaps` into prompt contexts.

#### [MODIFY] [ai_prompt_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_prompt_builder.py)
- Updated advisory-only constraints: Copilot is physically blocked from mutating detection rules (creating, modifying, disabling, or mapping techniques).

---

### API Gateway

#### [NEW] [detections.py](file:///c:/Users/Aditya/AegisX/backend/src/api/v1/routers/detections.py)
Exposes REST endpoints:
- `GET /api/v1/detections`
- `GET /api/v1/detections/{id}`
- `GET /api/v1/detections/coverage`
- `GET /api/v1/detections/gaps`
- `GET /api/v1/detections/uncovered`
- `GET /api/v1/detections/summary`
- `POST /api/v1/detections`
- `POST /api/v1/detections/{id}/disable`
- `POST /api/v1/detections/{id}/deprecate`

#### [MODIFY] [main.py](file:///c:/Users/Aditya/AegisX/backend/src/main.py)
- Mount the new `detections` router.

---

## Verification Plan

### Automated Tests
Execute integration tests:
```bash
.venv\Scripts\pytest backend/tests/integration/test_detections.py
```
Includes 30+ tests, including all mandatory tests:
- `test_detection_auto_creation()`, `test_detection_fingerprint_stability()`, `test_detection_sync_preserves_identity()`.
- `test_detection_history_preserved()`, `test_detection_disable_transition()`, `test_detection_deprecate_transition()`.
- `test_attack_mapping_change_detection()`, `test_coverage_score_calculation()`, `test_uncovered_techniques_detection()`.
- `test_detection_gap_detection()`, `test_detection_coverage_regression()`, `test_detection_drift_detection()`.
- `test_snapshot_rebuild_consistency()`, `test_detection_identity_preserved_after_disable()`, `test_detection_identity_preserved_after_deprecation()`.
- `test_ai_context_detection_injection()`, `test_rbac_detection_scope_validation()`.

We will maintain code coverage `>= 85%` for the new modules.

### Manual Verification
- Verify that standard operators are restricted from viewing or mutating detections outside their allowed scopes.
