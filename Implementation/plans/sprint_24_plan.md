# Sprint 24 — Implementation Plan

> **Paste your implementation plan for Sprint 24 below this line.**
> Delete this placeholder text when adding your content.

Sprint 24 Implementation Plan: Security Posture Management & Cyber Risk Intelligence

Transform AegisX into a production-grade Security Posture Management & Cyber Risk Intelligence Platform. Introduce in-memory posture management, risk scoring, organizational prioritization, drift detection, and snapshot caching, keeping full backward compatibility with Sprints 1–23.

User Review Required

Hardening Rules

[!IMPORTANT]1. Security Posture Identity Preservation RuleUnder security_posture_service.py:If synchronization generates the same posture fingerprint, preserve posture_id, ownership, history, drift history, creation timestamps, and risk scoring history. Do not create duplicate posture records. A new posture may only be created if:

category changes

asset changes

risk_source changes

2. Security Posture Terminal State RuleUnder security_posture_service.py:CLOSED is a terminal state.Requirements:

synchronization cannot reopen CLOSED postures

worker refresh cycles cannot reopen CLOSED postures

drift processing cannot reopen CLOSED postures

snapshot rebuilds cannot reopen CLOSED posturesA new posture may only be created if the fingerprint changes.

3. Risk Correlation Preservation RuleUnder risk_correlation_service.py:Correlation references are historical intelligence records. Existing correlations must never be deleted, modified, or overwritten. New correlation observations append records. Historical correlation timelines must survive posture closure, mitigation, synchronization, and snapshot rebuilds.

4. Risk Score Stability RuleUnder risk_intelligence_service.py:Risk score calculations must be deterministic. Given identical findings, exposures, incidents, detections, hunts, and threat intelligence, the same risk score must always be produced. Snapshot rebuilds, worker refreshes, and synchronization cycles must not alter calculated risk values.

5. Executive Intelligence Preservation RuleUnder security_posture_snapshot_service.py:Executive metrics are derived intelligence. They must never be stored as authoritative records. If snapshots are deleted, organizational_risk_score, security_posture_score, critical_risk_count, and risk_trends must be rebuilt dynamically from active posture records.

Proposed Changes

Domain Models

[NEW] security_posture.py

Create domain entities, status/severity/category enums, and response schemas:

Enums:

PostureSeverity (LOW, MEDIUM, HIGH, CRITICAL)

RiskStatus (OPEN, ACCEPTED, MITIGATED, CLOSED)

RiskCategory (ATTACK_SURFACE, VULNERABILITY, DETECTION_GAP, THREAT_EXPOSURE, COMPLIANCE, IDENTITY, CONFIGURATION, OPERATIONAL)

Schemas:

SecurityPostureResponse (contains: posture_id, posture_fingerprint, title, description, posture_score, risk_score, severity, category, status, owner, asset_id, risk_source, scope_id, created_at, updated_at)

RiskResponse (contains: risk_id, risk_fingerprint, title, description, category, severity, likelihood, impact, risk_score, status, created_at, updated_at)

PostureHistoryEntry (contains: posture_id, timestamp, event_type, details)

Registries

[NEW] security_posture_registry.py

Provide classification registry to validate posture categories against RiskCategory enum.

[NEW] risk_category_registry.py

Map supported threat, compliance, identity, surface, and configuration classifications.

[NEW] risk_severity_registry.py

Standardize risk level thresholds and resolve highest severity from active posture findings.

Fingerprinting

[NEW] posture_fingerprint_service.py

Implement stable security posture fingerprinting using SHA-256(category:asset_id:normalized_risk_source).

Core Services

[NEW] posture_history_service.py

Implement append-only, deepcopied, immutable history mapping for postures. Track events: CREATED, VALIDATED, ACCEPTED, MITIGATED, CLOSED, SCORE_CHANGED, RISK_CHANGED, DRIFT_DETECTED.

[NEW] security_posture_service.py

Handle posture creation, state transitions, scoring, and asset-based posture synchronization (sync_postures). Ensure identity preservation and terminal state enforcement.

[NEW] risk_intelligence_service.py

Aggregate risk across findings, active acceptances, exposures, alerts, incidents, cases, detections, IOCs, hunts, and purple team emulations. Calculate likelihood, impact, and risk_score in a fully deterministic manner.

[NEW] risk_prioritization_service.py

Sort and prioritize posture records based on threat context, severity weights, and business impact categories.

[NEW] risk_correlation_service.py

Maintain immutable mapping references between postures and external system findings or incidents.

[NEW] posture_drift_service.py

Compare current posture scores and counts against a cached baseline to identify RISK_INCREASED, RISK_DECREASED, POSTURE_CHANGED, EXPOSURE_INCREASED, EXPOSURE_DECREASED, and COVERAGE_CHANGED events.

[NEW] security_posture_snapshot_service.py

Generate, query, and dynamically rebuild posture snapshots (organizational risk scores, active posture grades, trends, counts) if the cached memory is deleted or corrupted.

Celery Worker Integration

[MODIFY] worker.py

Insert security posture processing logic right after exposure management inside the Celery execution loop. Catch all errors gracefully to prevent pipeline interruptions.

AI Copilot Context & Prompt Integration

[MODIFY] ai_context_builder.py

Add context generation methods _build_security_posture_context_block and _build_global_security_posture_context_block. Inject metrics, drifts, summaries, and trends into:

build_asset_context

build_finding_context

build_incident_context

build_case_context

build_executive_context

[MODIFY] ai_prompt_builder.py

Inject prompt instruction constraints to enforce that the AI Security Copilot cannot mutate security posture state, alter scores, or accept/mitigate/close cyber risks.

API Gateway

[NEW] security_posture.py

Expose standard REST endpoints:

GET /api/v1/security-posture (lists postures with ownership filter)

GET /api/v1/security-posture/open (lists open postures)

GET /api/v1/security-posture/critical (lists critical postures)

GET /api/v1/security-posture/drift (lists drift events)

GET /api/v1/security-posture/summary (rebuilds and returns the summary snapshot)

GET /api/v1/security-posture/{id} (fetches details of a specific posture)

POST /api/v1/security-posture (manually creates a posture)

POST /api/v1/security-posture/{id}/accept (transitions status to ACCEPTED)

POST /api/v1/security-posture/{id}/mitigate (transitions status to MITIGATED)

POST /api/v1/security-posture/{id}/close (transitions status to CLOSED - terminal state)

[MODIFY] main.py

Import and register the security posture router prefix /api/v1/security-posture.

Verification & Testing

[NEW] test_security_posture.py

Implement between 75 and 80 comprehensive integration tests. Key mandatory test cases:

test_posture_auto_creation()

test_posture_fingerprint_stability()

test_posture_sync_preserves_identity()

test_posture_duplicate_prevention()

test_posture_accept_transition()

test_posture_mitigate_transition()

test_posture_close_transition()

test_posture_identity_preserved_after_acceptance()

test_posture_identity_preserved_after_mitigation()

test_posture_identity_preserved_after_closure()

test_posture_terminal_state_enforcement()

test_posture_terminal_state_not_reactivated_by_sync()

test_posture_history_preserved()

test_risk_score_calculation()

test_risk_score_stability()

test_risk_prioritization()

test_risk_correlation_findings()

test_risk_correlation_exposures()

test_risk_correlation_incidents()

test_risk_correlation_cases()

test_risk_correlation_hunts()

test_risk_correlation_detections()

test_risk_correlation_campaigns()

test_risk_correlation_actors()

test_risk_correlation_preservation()

test_posture_drift_detection()

test_risk_increase_detection()

test_risk_decrease_detection()

test_snapshot_rebuild_consistency()

test_snapshot_rebuild_after_cache_deletion()

test_snapshot_rebuild_after_cache_corruption()

test_executive_risk_metrics_rebuild()

test_ai_context_posture_injection()

test_ai_advisory_only_enforcement()

test_rbac_scope_validation()

Verification Plan

Automated Tests

Run posture tests:

.venv\Scripts\pytest backend/tests/integration/test_security_posture.py

Run full regression suite:

.venv\Scripts\pytest

Manual Verification

Deploy local developer app, execute Celery worker pipeline mock, and call REST endpoints to verify correct JSON responses and proper RBAC restrictions.