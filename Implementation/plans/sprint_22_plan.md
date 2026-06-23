# Sprint 22 — Implementation Plan

> **Paste your implementation plan for Sprint 22 below this line.**
> Delete this placeholder text when adding your content.

Sprint 22: Purple Team & ATT&CK Validation Intelligence

Transform AegisX from a Threat Hunting Intelligence Platform into a Purple Team & ATT&CK Validation Intelligence Platform by introducing Purple Team Exercise Management, Adversary Emulation Intelligence, ATT&CK Validation Intelligence, Detection Validation Intelligence, Control Validation Intelligence, Validation Findings Intelligence, Coverage Analytics, Validation Drift Detection, and Purple Team Intelligence Snapshots.

User Review Required

[!IMPORTANT]The exercise state CLOSED is a terminal state. Once an exercise transitions to CLOSED, it cannot be reopened, reactivated, or modified, and subsequent worker synchronizations or snapshot rebuilds will not modify it.

[!IMPORTANT]Validation Identity Preservation Rule:If validation execution is rerun and generates the same exercise_id, technique_id, and validation target, preserve validation_id, validation history, timestamps, and findings linkage, and do not create duplicate validation records. A new validation record should only be created if:

technique changes

exercise changes

validation target changes

This prevents duplicate validation artifacts after worker refreshes.

[!WARNING]No external emulation engines or validation platforms (such as MITRE Caldera, Atomic Red Team Execution Engines, Prelude Operator, SCYTHE, etc.) will be integrated. The platform operates offline and remains registry-driven and in-memory.

Open Questions

[!NOTE]There are no outstanding open questions, as the requirements map out all specific models, enums, transition paths, registries, services, and tests precisely.

Proposed Changes

Domain Models

[NEW] purple_team.py

Define enums and Pydantic schemas:

ExerciseSeverity: LOW, MEDIUM, HIGH, CRITICAL

ExerciseStatus: OPEN, ACTIVE, UNDER_REVIEW, COMPLETED, CLOSED

ExerciseType: ATTACK_SIMULATION, ADVERSARY_EMULATION, CONTROL_VALIDATION, DETECTION_VALIDATION

ValidationStatus: PASSED, PARTIAL, FAILED

PurpleTeamExerciseResponse:

exercise_id: uuid.UUID

exercise_fingerprint: str

name: str

description: str

exercise_type: ExerciseType

severity: ExerciseSeverity

status: ExerciseStatus

owner: Optional[str]

scope_id: uuid.UUID

created_at: datetime

updated_at: datetime

ValidationResponse:

validation_id: uuid.UUID

exercise_id: uuid.UUID

technique_id: str

validation_status: ValidationStatus

expected_detection: bool

actual_detection: bool

coverage_gap: bool

created_at: datetime

updated_at: datetime

PurpleTeamFindingResponse:

finding_id: uuid.UUID

exercise_id: uuid.UUID

technique_id: str

severity: ExerciseSeverity

gap_type: str

description: str

created_at: datetime

PurpleTeamHistoryEntry:

exercise_id: uuid.UUID

timestamp: datetime

event_type: str

details: str

Registries

[NEW] exercise_type_registry.py

Validation logic for ExerciseType.

[NEW] validation_status_registry.py

Validation logic for ValidationStatus enums.

[NEW] attack_validation_registry.py

Pre-seed ATT&CK techniques: T1059, T1562, T1078, T1027, T1105, T1047, T1055 (fully offline and registry-driven).

Fingerprinting

[NEW] purple_team_fingerprint_service.py

Generate fingerprint: SHA256(exercise_type, normalized_name, sorted_related_techniques, sorted_related_entities).

Purple Team Fingerprint Stability Rule: Fingerprint remains stable across ownership changes, status changes, validation executions, findings creation, coverage updates, drift, and snapshot rebuilds. Changes only when exercise_type, exercise name, related techniques, or related entities change.

Core Services

[NEW] purple_team_history_service.py

Append-only immutable log for tracking: CREATED, ACTIVATED, REVIEWED, VALIDATED, COMPLETED, CLOSED, FINDING_CREATED, COVERAGE_CHANGED.

Purple Team History Preservation Rule: History is immutable, copy-safe (utilizing deepcopy), never deleted or modified. Must survive execution, completion, closure, sync, and snapshot rebuilds.

[NEW] purple_team_service.py

Manages exercise creation, synchronization, lifecycle transitions, and owner assignment.

Purple Team State Machine:

OPEN -> ACTIVE

ACTIVE -> UNDER_REVIEW or COMPLETED

UNDER_REVIEW -> ACTIVE or COMPLETED

COMPLETED -> CLOSED

Purple Team Terminal State Rule: CLOSED status is terminal. Re-execution, re-opening, activation, worker sync, or snapshot updates cannot modify closed exercises. New exercise created only if fingerprint changes.

[NEW] adversary_emulation_service.py

Manages adversary emulation intelligence models for APT29, APT28, Lazarus, and FIN7.

Maps validation techniques to detections, hunts, incidents, and cases.

[NEW] attack_validation_service.py

Validate ATT&CK techniques against active Detections, Alerts, Incidents, Cases, and Hunts.

Produces outcomes: PASSED, PARTIAL, FAILED.

[NEW] detection_validation_service.py

Performs expected detection, actual detection, and detection effectiveness validation, returning validation status.

[NEW] purple_team_finding_service.py

Handles validation, coverage, control, and detection findings.

Validation Finding Preservation Rule: Append-only, copy-safe, immutable findings records. Must survive completion, closure, syncs, and snapshot rebuilds.

[NEW] purple_team_coverage_service.py

Compute coverage analytics: attack_coverage, actor_coverage, campaign_coverage, detection_validation_coverage, control_validation_coverage.

[NEW] purple_team_drift_service.py

Detects regression events: VALIDATION_REGRESSION, COVERAGE_REGRESSION, DETECTION_DRIFT, CONTROL_DRIFT, NEW_ATTACK_GAP.

Emits purple_team.drift and purple_team.coverage_changed workflow events.

[NEW] purple_team_snapshot_service.py

Rebuildable cache containing total exercises, status counts, passed/partial/failed validation counts, and coverage metrics.

Purple Team Snapshot Consistency Rule: Cache-only and rebuildable. If deleted, corrupted, or missing, the cache must rebuild dynamically from active exercise records.

Integrations

[MODIFY] worker.py

Gracefully trigger Purple Team synchronization, adversary emulation execution, validation runs, coverage calculations, drift alerts, and snapshots generation at the end of the Celery worker task execution chain.

[MODIFY] ai_context_builder.py

Inject Purple Team metrics, validation results, and findings summary block into asset, finding, incident, case, and executive profiles.

[MODIFY] ai_prompt_builder.py

Add prompt constraints enforcing that the Security Copilot is advisory-only and cannot mutate/create/activate/escalate/close exercises, validations, or findings.

API Gateway

[NEW] purple_team.py

Expose REST API endpoints:

GET /api/v1/purple-team/exercises

GET /api/v1/purple-team/exercises/{id}

GET /api/v1/purple-team/exercises/active

GET /api/v1/purple-team/exercises/completed

GET /api/v1/purple-team/validations

GET /api/v1/purple-team/findings

GET /api/v1/purple-team/coverage

GET /api/v1/purple-team/drift

GET /api/v1/purple-team/summary

POST /api/v1/purple-team/exercises

POST /api/v1/purple-team/exercises/{id}/activate

POST /api/v1/purple-team/exercises/{id}/review

POST /api/v1/purple-team/exercises/{id}/complete

POST /api/v1/purple-team/exercises/{id}/close

Enforce standard role-based access checks and scope-level owner validations wrapped in StandardResponse.

[MODIFY] main.py

Register the /api/v1/purple-team router.

Verification Plan

Automated Tests

Run pytest backend/tests/integration/test_purple_team.py to execute a minimum of 50 integration tests, including:

test_exercise_auto_creation()

test_exercise_fingerprint_stability()

test_exercise_sync_preserves_identity()

test_exercise_activate_transition()

test_exercise_review_transition()

test_exercise_complete_transition()

test_exercise_close_transition()

test_exercise_terminal_state_enforcement()

test_history_preserved()

test_validation_passed()

test_validation_partial()

test_validation_failed()

test_validation_identity_preserved()

test_validation_sync_preserves_identity()

test_apt29_emulation()

test_apt28_emulation()

test_lazarus_emulation()

test_fin7_emulation()

test_actor_mapping_preserved()

test_campaign_mapping_preserved()

test_validation_finding_creation()

test_validation_finding_preservation()

test_gap_finding_creation()

test_attack_coverage_calculation()

test_actor_coverage_calculation()

test_campaign_coverage_calculation()

test_detection_validation_coverage()

test_control_validation_coverage()

test_coverage_regression_detection()

test_validation_drift_detection()

test_detection_drift_detection()

test_control_drift_detection()

test_new_attack_gap_detection()

test_snapshot_rebuild_consistency()

test_snapshot_rebuild_after_cache_deletion()

test_snapshot_rebuild_after_corruption()

test_ai_context_purple_team_injection()

test_ai_advisory_only_enforcement()

test_rbac_scope_validation()

test_rbac_operator_permissions()

test_rbac_reader_restrictions()

test_identity_preserved_after_completion()

test_identity_preserved_after_closure()

test_validation_identity_preserved_after_recalculation()

test_validation_identity_preserved_after_worker_sync()

Verification of registries, duplicates prevention, Celery integrations, and coverage metrics.

Execute full test suite pytest to ensure zero regressions across Sprints 1–22.