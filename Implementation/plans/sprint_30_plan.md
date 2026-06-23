# Sprint 30 — Implementation Plan

> **Paste your implementation plan for Sprint 30 below this line.**
> Delete this placeholder text when adding your content.

Implementation Plan - Sprint 30: Cyber Risk Quantification Intelligence

Transform AegisX from a Security Operations Analytics Intelligence Platform into a Cyber Risk Quantification Intelligence Platform.

User Review Required

[!IMPORTANT]

All risk records, scenarios, histories, forecasts, and snapshots operate strictly in-memory.

Zero database migrations.

Zero external integrations.

AI Security Copilot remains advisory-only.

Architectural Constraints (Sprint 1–29 Compliance)

Registry-driven design: All scenarios, frequencies, and impacts must be validated against registries.

Deterministic fingerprinting: Risk fingerprints must be generated using SHA-256 and remain stable.

Identity preservation: Re-syncs and updates must preserve the unique identifiers of risks.

Terminal-state enforcement: Closed risks must never transition back to any active states.

Immutable historical records: History entries must never be modified, deleted, or reordered.

Snapshot rebuild consistency: Snapshots are non-authoritative caches and must be fully rebuildable from active source data.

In-memory storage only: No database migrations.

No external integrations: No FAIR integrations, financial APIs, or external risk calculation engines.

No breaking API changes: Keep all existing endpoints and routers backward compatible.

Full backward compatibility: Guarantee that all previous sprints (1-29) run without regression.

AI Advisory-only enforcement: Physically block the AI Security Copilot from executing any risk mutations.

Lifecycle & Hardening Rules

Cyber Risk Terminal State Rule

CLOSED is a terminal state.

Requirements:

synchronization cannot reopen CLOSED risks

worker refresh cycles cannot reopen CLOSED risks

forecasting cannot reopen CLOSED risks

drift processing cannot reopen CLOSED risks

snapshot rebuilds cannot reopen CLOSED risks

A new quantified risk may only be created if the fingerprint changes.

Cyber Risk Synchronization Rule

If synchronization generates an identical fingerprint:

preserve risk_id

preserve fingerprint

preserve created_at

preserve updated_at

preserve history

preserve trend history

preserve forecast history

Do not create duplicates.Do not create replacement records.Return the existing quantified risk.

Cyber Risk Identity Preservation Rule

If synchronization generates an identical fingerprint:

preserve risk_id

preserve fingerprint

preserve created_at

preserve history

preserve trend history

preserve forecast history

Do not create duplicates.

Risk History Preservation Rule

History entries are immutable.

Requirements:

never modify history

never delete history

never reorder history

History must survive:

worker refreshes

forecasting

snapshot rebuilds

drift processing

History is the authoritative audit trail.

History must never be reconstructed from:

risk state

forecast state

trend state

snapshots

Only append new events.

Risk Forecast Preservation Rule

Forecasts are derived intelligence.

Requirements:

forecasts must be deterministic

forecasts must be reproducible

forecasts must survive worker refreshes

forecasts must survive snapshot rebuilds

forecasts must never modify risk state

forecasts must never modify history

Forecasts are not authoritative state.

Risk Calculation Determinism Rule

Risk calculations are derived intelligence.

Requirements:

SLE calculations must be deterministic

ALE calculations must be deterministic

residual risk calculations must be deterministic

mitigation effectiveness calculations must be deterministic

Identical inputs must always produce identical outputs.

Calculations must never mutate:

risk records

history

forecasts

snapshots

Calculations are read-only intelligence generation.

Quantified Risk Snapshot Consistency Rule

Snapshots are:

cache-only

rebuildable

non-authoritative

If cache is:

missing

deleted

corrupted

generate_snapshot() and get_snapshot() must rebuild from source intelligence.

No risk state may exist exclusively inside snapshots.

Snapshots are derived intelligence only.

Source risk records remain the authoritative source of truth.

Proposed Changes

Domain Models

[NEW] cyber_risk_quantification.py

Define enums:

RiskSeverity (LOW, MEDIUM, HIGH, CRITICAL)

RiskQuantificationStatus (ACTIVE, ACCEPTED, MITIGATED, CLOSED)

RiskScenarioType (DATA_BREACH, RANSOMWARE, INSIDER_THREAT, SERVICE_OUTAGE, CLOUD_COMPROMISE, SUPPLY_CHAIN)

Define Pydantic models:

CyberRiskResponse: Represents a quantified risk entry.

RiskScenarioResponse: Scenarios with frequency, impact, and expected loss.

RiskForecastResponse: Projected risk, reduction, and exposure.

RiskHistoryEntry: Audit history records.

Registries

[NEW] risk_scenario_registry.py

Pre-seeded scenarios: DATA_BREACH, RANSOMWARE, INSIDER_THREAT, SERVICE_OUTAGE, CLOUD_COMPROMISE, SUPPLY_CHAIN.

Provide registry-driven scenario validation.

[NEW] risk_frequency_registry.py

Pre-seeded frequencies: RARE (ARO = 0.05), OCCASIONAL (ARO = 0.2), LIKELY (ARO = 1.0), FREQUENT (ARO = 3.0).

[NEW] risk_impact_registry.py

Pre-seeded impacts: LOW (Factor = 0.1), MEDIUM (Factor = 0.3), HIGH (Factor = 0.6), CRITICAL (Factor = 0.9).

Fingerprinting

[NEW] risk_quantification_fingerprint_service.py

Computes SHA-256 of scenario_type, scope_id, and normalized_title.

Stability enforcement: must not change during recalculations or worker updates.

Core Services

[NEW] risk_history_service.py

Immutable history recorder for CREATED, ACCEPTED, MITIGATED, CLOSED, ALE_CHANGED, RESIDUAL_RISK_CHANGED, FORECAST_CHANGED, DRIFT_DETECTED.

Enforces deep-copying on retrieval.

[NEW] cyber_risk_quantification_service.py

Implements lifecycle transitions, duplicate prevention, and sync logic.

[NEW] loss_expectancy_service.py

Calculates Single Loss Expectancy (SLE = Asset Value * Exposure Factor) and Annualized Loss Expectancy (ALE = SLE * ARO).

[NEW] residual_risk_service.py

Computes inherent/residual risks and mitigation effectiveness.

[NEW] risk_forecast_service.py

Generates deterministic 4-quarter risk forecasts.

[NEW] risk_trend_service.py

Calculates and stores deterministic history trends for risk exposure.

[NEW] risk_drift_service.py

Compares risk parameters against baseline trends. Emits risk.drift and risk.forecast_changed events.

[NEW] risk_quantification_snapshot_service.py

Manages cache-only snapshots. Automatically rebuilds from active risks on cache deletion/corruption.

Integrations

[MODIFY] worker.py

Add periodic background tasks executing risk synchronization, forecasts, drift checks, and snapshot updates. Include grace-handling to protect the worker thread.

Sprint 30 Worker Execution Order

The worker integration must execute in the following order:

CyberRiskQuantificationService.sync_risks()

LossExpectancyService.calculate()

ResidualRiskService.calculate()

RiskForecastService.calculate()

RiskTrendService.calculate()

RiskDriftService.process_drift()

RiskQuantificationSnapshotService.generate_snapshot()

Failures must be isolated so that one service failure does not prevent remaining Sprint 30 services from executing.

[MODIFY] ai_context_builder.py

Inject risk quantification summaries, ALE, residual risk, forecasts, and snapshots into all AI contexts (asset, finding, incident, executive, resilience, analytics).

[MODIFY] ai_prompt_builder.py

Append instructions blocking AI Copilot mutations to cyber risk quantification.

[MODIFY] main.py

Register cyber_risk_quantification router.

API Gateway

[NEW] cyber_risk_quantification.py

GET endpoints: /, /open, /critical, /forecasts, /trends, /drift, /summary, /{id}.

POST endpoints: /, /{id}/accept, /{id}/mitigate, /{id}/close.

Enforces RBAC (admin, operator, reader) and scope isolation checks.

Verification Plan

Automated Tests

Implement minimum of 110+ integration tests in test_cyber_risk_quantification.py.

Coverage Target: >= 85% code coverage.

Mandatory Test Cases

test_risk_auto_creation()

test_risk_fingerprint_stability()

test_risk_sync_preserves_identity()

test_risk_accept_transition()

test_risk_mitigate_transition()

test_risk_close_transition()

test_risk_terminal_state_enforcement()

test_risk_history_preserved()

test_risk_history_immutable()

test_sle_calculation()

test_ale_calculation()

test_residual_risk_calculation()

test_forecast_generation()

test_forecast_deterministic()

test_risk_trend_generation()

test_risk_drift_detection()

test_snapshot_rebuild_consistency()

test_snapshot_rebuild_after_cache_deletion()

test_snapshot_rebuild_after_cache_corruption()

test_snapshot_not_authoritative()

test_ai_context_risk_injection()

test_ai_advisory_only_enforcement()

test_rbac_risk_scope_validation()

test_worker_integration()

test_closed_risk_not_reactivated_by_worker()

test_closed_risk_not_reactivated_by_forecast()

test_closed_risk_not_reactivated_by_snapshot()

test_closed_risk_not_reactivated_by_drift()

test_risk_identity_preserved_after_worker_refresh()

test_risk_identity_preserved_after_forecast_refresh()

test_risk_identity_preserved_after_snapshot_rebuild()

test_risk_identity_preserved_after_drift_processing()

Additional Coverage Areas

Registry validation (frequency, impact, scenarios).

Duplicate prevention mechanisms on creation.

History preservation across drift analysis.

Trend history limit and retrieval verification.

Scope isolation boundaries between scopes.

Cache invalidation and snapshot regeneration behavior.

Forecast consistency across worker refreshes.

Identity preservation during synchronizations.

Run:

.venv\Scripts\pytest backend/tests/integration/test_cyber_risk_quantification.py
.venv\Scripts\pytest

Deliverables

Upon completion provide:

1. Architecture Summary

Detail the quantified risk lifecycle, ALE architecture, residual risk logic, forecasting engine, and drift detection details.

2. File Manifest

List of all new and modified files.

3. Testing Results

Exact execution commands and test suite results.

4. Verification Summary

Confirm terminal-state rules, fingerprint stability, history preservation, snapshot reconstruction, and AI advisory enforcement.

5. Backward Compatibility Statement

Verification of zero regressions across Sprint 1-29 features.

After creating the implementation plan:

STOP.

Wait for approval before implementation.