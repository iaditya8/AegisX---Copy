Implementation Plan - Sprint 35: Security Decision Intelligence

Transform AegisX from a Unified Security Intelligence Graph Platform into a Security Decision Intelligence Platform.

User Review Required

[!IMPORTANT]

All decisions, recommendations, cost-benefit tradeoff matrices, impact evaluations, histories, and snapshots operate strictly in-memory.

Zero database migrations.

Zero external decision platforms.

Zero financial modeling engines.

AI Security Copilot remains strictly advisory-only and cannot commit or execute security decisions.

Architectural Constraints (Sprint 1–35 Compliance)

Registry-driven design: All decision categories, cost tiers, impact severities, and tradeoff metrics must be validated against registries.

Deterministic fingerprinting: Decision fingerprints must be generated using SHA-256 and remain stable.

Identity preservation: Syncs and calculations must preserve unique decision recommendation identifiers.

Terminal-state enforcement: ARCHIVED decisions must never transition back to active/pending states.

Immutable historical records: History entries must never be modified, deleted, or reordered.

Snapshot rebuild consistency: Snapshots are non-authoritative caches and must be fully rebuildable from active source data.

In-memory storage only: Zero database migrations.

No external integrations: Zero external calculators.

No breaking API changes: Keep all existing endpoints and routers backward compatible.

Full backward compatibility: Guarantee that all previous sprints (1-34) run without regression.

AI Advisory-only enforcement: Physically block the AI Security Copilot from executing any decision mutations.

Lifecycle & Hardening Rules

Decision Terminal State Rule

ARCHIVED is a terminal state.

Requirements:

synchronization cannot reactivate ARCHIVED decisions

worker refresh cycles cannot reactivate ARCHIVED decisions

tradeoff mapping updates cannot reactivate ARCHIVED decisions

impact scoring calculations cannot reactivate ARCHIVED decisions

drift processing cannot reactivate ARCHIVED decisions

snapshot rebuilds cannot reactivate ARCHIVED decisions

A new decision may only be created if the fingerprint changes.

Decision Identity Preservation Rule

If synchronization generates an identical fingerprint:

preserve decision_id

preserve fingerprint

preserve created_at

preserve history

preserve tradeoff_matrix

preserve impact_metrics

Do not create duplicates.

Decision History Preservation Rule

History entries are immutable.

Requirements:

never modify history

never delete history

never reorder history

History must survive:

worker refreshes

tradeoff scoring

impact calculations

drift processing

snapshot rebuilds

History is the authoritative audit trail. Only append new events.

Decision Scoring Determinism Rule

Decision calculations are derived intelligence.

Requirements:

cost-benefit tradeoff matrix calculations must be deterministic

risk reduction estimation must be deterministic

operational impact calculation must be deterministic

confidence score calculations must be deterministic

Identical inputs must always produce identical outputs.

Calculations must never mutate:

decision records

histories

tradeoffs

snapshots

Calculations are read-only intelligence generation.

Decision Snapshot Consistency Rule

Snapshots are:

cache-only

rebuildable

non-authoritative

If cache is:

missing

deleted

corrupted

generate_snapshot() and get_snapshot() must rebuild from source decision recommendations.No state may exist exclusively inside snapshots. Source decision records remain authoritative.

Proposed Changes

Domain Models

[NEW] security_decision.py

Define enums:

DecisionImpact (LOW, MEDIUM, HIGH, CRITICAL)

DecisionStatus (ACTIVE, RECOMMENDED, COMMITTED, ARCHIVED)

DecisionType (REMEDIATION, MITIGATION, TRANSFER, ACCEPTANCE, COMPLIANCE_CONTROL)

Define Pydantic models:

DecisionResponse: Represents a generated decision option.

DecisionTradeoffResponse: Detailed cost-benefit-risk analysis.

DecisionImpactResponse: Impact metrics on system baseline.

DecisionSnapshotResponse: Statistics of decisions.

DecisionHistoryEntry: Audit logs.

Registries

[NEW] decision_type_registry.py

Pre-seeded: REMEDIATION, MITIGATION, TRANSFER, ACCEPTANCE, COMPLIANCE_CONTROL.

[NEW] decision_impact_registry.py

Pre-seeded: LOW, MEDIUM, HIGH, CRITICAL.

[NEW] tradeoff_factor_registry.py

Pre-seeded: cost-benefit parameters (cost_multiplier, risk_reduction_coefficient).

Fingerprinting

[NEW] decision_fingerprint_service.py

Generates SHA256(decision_type + "_" + str(target_entity_id) + "_" + option_name.strip().lower()) stable fingerprint.

Core Services

[NEW] decision_history_service.py

Immutable append-only history tracking CREATED, CALCULATED, RECOMMENDED, COMMITTED, DRIFT_DETECTED, ARCHIVED.

[NEW] security_decision_service.py

Handles decision option generation, lifecycle transitions, commit actions, and duplicates.

Enforces Decision Terminal State Rule.

[NEW] decision_tradeoff_service.py

Computes deterministic cost-benefit-risk tradeoffs leveraging Sprint 34 Unified Security Intelligence Graph correlation data.

[NEW] decision_drift_service.py

Identifies staleness or change in tradeoff parameters. Emits decision.drift and decision.status_changed.

[NEW] decision_snapshot_service.py

Cache-only snapshot rebuild engine from active decision records.

Integrations

[MODIFY] worker.py

Add periodic background tasks for decision recommendation generation, tradeoff metric recalculation, drift analysis, and snapshot updates.

Sprint 35 Worker Execution Order

SecurityDecisionService.sync_decision_recommendations()

DecisionTradeoffService.calculate()

DecisionDriftService.process_drift()

DecisionSnapshotService.generate_snapshot()

[MODIFY] ai_context_builder.py

Inject decision lists, tradeoff matrices, estimated risk reductions, and decision drift summaries into AI contexts.

[MODIFY] ai_prompt_builder.py

Prompt guardrails blocking AI Copilot mutations to decisions, tradeoff scores, or committed status.

[MODIFY] main.py

Register security_decision API router.

API Gateway

[NEW] security_decision.py

POST: /, /{id}/recommend, /{id}/commit, /{id}/archive.

GET: /, /recommended, /committed, /drift, /summary, /{id}.

Enforces RBAC and scope isolation.

Verification Plan

Automated Tests

Implement 110+ integration tests in test_security_decision.py.Coverage target: >= 85% code coverage.

Sprint 35 Mandatory Test Cases

test_decision_auto_creation()

test_decision_fingerprint_stability()

test_decision_identity_preservation()

test_decision_duplicate_prevention()

test_decision_commit_transition()

test_decision_recommend_transition()

test_decision_archive_transition()

test_decision_terminal_state_enforcement()

test_archived_decision_not_reactivated_by_sync()

test_archived_decision_not_reactivated_by_worker()

test_archived_decision_not_reactivated_by_snapshot()

test_archived_decision_not_reactivated_by_drift()

test_archived_decision_not_reactivated_by_tradeoff()

test_decision_history_preserved()

test_decision_history_immutable()

test_decision_history_order_preserved()

test_tradeoff_matrix_deterministic()

test_operational_impact_estimation()

test_risk_reduction_calculation()

test_decision_drift_detection()

test_decision_drift_clearing()

test_snapshot_rebuild_consistency()

test_snapshot_rebuild_after_cache_deletion()

test_snapshot_rebuild_after_cache_corruption()

test_snapshot_not_authoritative()

test_snapshot_rebuild_from_source_of_truth()

test_ai_context_decision_injection()

test_ai_advisory_only_enforcement()

test_rbac_decision_scope_validation()

test_worker_integration()

test_decision_identity_preserved_after_worker_refresh()

test_decision_identity_preserved_after_tradeoff_refresh()

test_decision_identity_preserved_after_snapshot_rebuild()

test_decision_identity_preserved_after_drift_processing()

test_tradeoff_score_determinism()

test_scope_isolation_for_tradeoffs()

test_decision_score_stability()

Run:

.venv\Scripts\pytest backend/tests/integration/test_security_decision.py
.venv\Scripts\pytest

Deliverables

1. Architecture Summary

Details of decision recommendations, cost-benefit calculations, drift tracking, and rebuildable snapshots.

2. File Manifest

List of all new and modified files.

3. Testing Results

Pytest verification outputs demonstrating zero regressions.

STOP.Wait for user approval before implementation.
