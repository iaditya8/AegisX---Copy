# Sprint 25 — Implementation Plan

> **Paste your implementation plan for Sprint 25 below this line.**
> Delete this placeholder text when adding your content.

Sprint 25: Control Validation & Security Effectiveness Intelligence

Transform AegisX into a production-grade Control Validation & Security Effectiveness Intelligence Platform. Introduce security control registries, validation tracking, effectiveness scoring, coverage analytics, drift detection, and snapshot caching, keeping full backward compatibility with Sprints 1–24.

User Review Required

Hardening Rules

[!IMPORTANT]1. Control Validation Source RuleUnder control_validation_service.py:Control validations must remain registry-driven and leverage only AegisX local data (Assets, Findings, Alerts, Incidents, Cases, Detections, ATT&CK Techniques, IOCs, Threat Actors, Campaigns, Hunts, Purple Team Exercises, Exposures, and Postures). No external validations (e.g. Defender, AttackIQ, Cymulate) or external APIs are allowed.

2. Control Identity Preservation RuleUnder control_validation_service.py:Re-running sync with identical control name, ATT&CK mappings, and control type must preserve control_id, ownership, validation history, effectiveness history, drift history, and creation timestamps. No duplicate control records will be created.

3. Control Terminal State RuleUnder control_validation_service.py:RETIRED is a terminal state. Synchronization, worker refreshes, effectiveness recalculations, drift processing, and snapshot rebuilds cannot reactivate or modify RETIRED controls.

4. Validation Preservation RuleUnder control_validation_service.py:Validation records are historical intelligence records. Existing validation results must never be deleted, modified, or overwritten. New validation runs append new records. They must survive control retirement, worker syncs, snapshot rebuilds, and coverage recalculations.

5. Effectiveness Score Stability RuleUnder effectiveness_scoring_service.py:Calculations must be deterministic. Given identical detections, ATT&CK mappings, purple team results, hunts, posture, and exposures, the same effectiveness score must always be produced. Refreshes, snapshot rebuilds, and sync runs must not alter calculated effectiveness values.

6. Control Fingerprint Stability RuleUnder control_fingerprint_service.py:Fingerprints are generated via SHA-256(control_name:sorted_attack_techniques:control_type). The fingerprint must change only if the control name, ATT&CK mappings, or control type changes. It must remain stable across scoring, validation execution, drift processing, worker refreshes, and snapshot rebuilds.

7. Control Validation Snapshot Consistency RuleUnder control_validation_snapshot_service.py:Snapshots are cache-only, rebuildable, and non-authoritative. If deleted or corrupted, they must rebuild dynamically from active control records without losing data.

8. Control Effectiveness History Preservation RuleUnder control_validation_service.py:Effectiveness calculations are historical intelligence records. Existing effectiveness history entries must never be deleted, modified, or overwritten. Recalculations append new effectiveness observations. Historical effectiveness records must survive: validation executions, effectiveness recalculations, drift processing, worker refresh cycles, coverage recalculations, snapshot rebuilds, and control retirement. This ensures executive trend reporting remains reproducible, drift analysis can compare previous/current effectiveness, and historical effectiveness degradation remains auditable.

Proposed Changes

Domain Models

[NEW] control_validation.py

Create domain entities, status/severity/category enums, and response schemas:

Enums:

ControlSeverity (LOW, MEDIUM, HIGH, CRITICAL)

ControlStatus (ACTIVE, DEGRADED, FAILED, RETIRED)

ValidationStatus (PASSED, PARTIAL, FAILED)

ControlType (DETECTION, PREVENTIVE, CORRECTIVE, COMPENSATING, MONITORING)

Pydantic Response Schemas:

ControlResponse (contains: control_id, control_fingerprint, name, description, control_type, severity, status, effectiveness_score, attack_techniques, scope_id, created_at, updated_at)

ValidationResponse (contains: validation_id, control_id, validation_status, effectiveness_score, attack_technique, evidence, created_at)

ControlHistoryEntry (contains: control_id, timestamp, event_type, details)

Registries

[NEW] control_type_registry.py

Validate control types against the ControlType enum.

[NEW] control_severity_registry.py

Standardize control severity levels and resolve highest severity level from a list.

[NEW] effectiveness_registry.py

Define effectiveness thresholds (EXCELLENT >= 90, GOOD >= 70, FAIR >= 50, POOR >= 20, FAILED < 20).

Fingerprinting

[NEW] control_fingerprint_service.py

Implement stable control fingerprinting using SHA-256(control_name:sorted_attack_techniques:control_type).

Core Services

[NEW] control_history_service.py

Implement append-only, deepcopied, immutable history mapping for controls. Track events: CREATED, VALIDATED, DEGRADED, FAILED, RETIRED, EFFECTIVENESS_CHANGED, COVERAGE_CHANGED, DRIFT_DETECTED.

[NEW] control_validation_service.py

Handle control creation, validation execution, validation aggregation, state transitions (retirement), and database synchronization (sync_controls). Keep controls and validations in-memory. Implement identity preservation and terminal state enforcement.

[NEW] effectiveness_scoring_service.py

Calculate control effectiveness_score, validation_score, attack_coverage_score, and control_health_score in a fully deterministic and stable manner based on validation records and platform coverage.

[NEW] control_coverage_service.py

Calculate ATT&CK coverage, Detection coverage, Purple Team coverage, Hunt coverage, and Exposure coverage across scopes.

[NEW] control_correlation_service.py

Maintain immutable mapping references between controls and detections, hunts, purple team exercises, exposures, or security posture records.

[NEW] control_drift_service.py

Compare current control effectiveness, status, and validation results against a cached baseline to identify CONTROL_DEGRADED, CONTROL_FAILED, EFFECTIVENESS_CHANGED, COVERAGE_CHANGED, and VALIDATION_REGRESSED events.

[NEW] control_validation_snapshot_service.py

Generate, query, and dynamically rebuild control snapshots (active/degraded/failed counts, average effectiveness, attack coverage, validation success rate) if the cached memory is deleted or corrupted.

Celery Worker Integration

[MODIFY] worker.py

Insert control validation processing logic right after security posture management inside the Celery execution loop. Call sync_controls, calculate effectiveness, calculate coverage, process_drift, and generate_snapshot. Catch all errors gracefully to prevent pipeline interruptions.

AI Copilot Context & Prompt Integration

[MODIFY] ai_context_builder.py

Add context generation methods _build_control_validation_context_block and _build_global_control_validation_context_block. Inject summaries, scores, coverage, failures, regressions, and drifts into:

build_asset_context

build_finding_context

build_incident_context

build_case_context

build_executive_context

[MODIFY] ai_prompt_builder.py

Inject prompt instruction constraints to enforce that the AI Security Copilot cannot mutate control states, retire controls, execute validations, or alter scores/results.

API Gateway

[NEW] control_validation.py

Expose standard REST endpoints:

GET /api/v1/control-validation (lists controls with ownership filter)

GET /api/v1/control-validation/active (lists active controls)

GET /api/v1/control-validation/degraded (lists degraded controls)

GET /api/v1/control-validation/failed (lists failed controls)

GET /api/v1/control-validation/drift (lists control drift events)

GET /api/v1/control-validation/coverage (lists control coverage statistics)

GET /api/v1/control-validation/summary (rebuilds and returns the summary snapshot)

GET /api/v1/control-validation/{id} (fetches details of a specific control)

POST /api/v1/control-validation (manually creates a control)

POST /api/v1/control-validation/{id}/validate (executes a validation against a control)

POST /api/v1/control-validation/{id}/retire (transitions status to RETIRED - terminal state)

[MODIFY] main.py

Import and register the control validation router prefix /api/v1/control-validation.

Verification & Testing

[NEW] test_control_validation.py

Implement between 80 and 85 comprehensive integration tests. Key mandatory test cases:

test_control_auto_creation()

test_control_fingerprint_stability()

test_control_sync_preserves_identity()

test_control_duplicate_prevention()

test_control_validation_execution()

test_control_validation_preservation()

test_control_effectiveness_calculation()

test_control_effectiveness_stability()

test_control_coverage_calculation()

test_control_drift_detection()

test_control_effectiveness_history_preserved()

test_control_effectiveness_history_survives_retirement()

test_control_effectiveness_history_survives_snapshot_rebuild()

test_control_effectiveness_history_append_only()

test_control_validation_regression_detection()

test_control_retire_transition()

test_control_terminal_state_enforcement()

test_control_terminal_state_not_reactivated_by_sync()

test_control_history_preserved()

test_control_correlation_preservation()

test_attack_coverage_calculation()

test_purple_team_validation_correlation()

test_hunt_validation_correlation()

test_security_posture_validation_correlation()

test_snapshot_rebuild_consistency()

test_snapshot_rebuild_after_cache_deletion()

test_snapshot_rebuild_after_cache_corruption()

test_ai_context_control_validation_injection()

test_ai_advisory_only_enforcement()

test_rbac_scope_validation()

Verification Plan

Automated Tests

Run control validation tests:

.venv\Scripts\pytest backend/tests/integration/test_control_validation.py

Run full regression suite:

.venv\Scripts\pytest

Manual Verification

Deploy local developer app, execute Celery worker pipeline mock, and call REST endpoints to verify correct JSON responses and proper RBAC restrictions.