Implementation Plan - Sprint 37: Unified Security Intelligence Fabric

Transform AegisX from an Autonomous Security Planning Intelligence Platform into a Unified Security Intelligence Fabric Platform.

User Review Required

[!IMPORTANT]

All intelligence fabric segments, propagation nodes, cross-domain score maps, histories, and snapshots operate strictly in-memory.

Zero database migrations.

Zero external middleware or event brokers.

Zero external RAG or vector systems.

AI Security Copilot remains strictly advisory-only and cannot alter confidence weights, flow parameters, or fabric configurations.

Architectural Constraints (Sprint 1–37 Compliance)

Registry-driven design: All intelligence streams, propagation routes, and confidence weights must be validated against registries.

Deterministic fingerprinting: Fabric configuration and propagation node fingerprints must be generated using SHA-256 and remain stable.

Identity preservation: Syncs and updates must preserve unique fabric channel and node identifiers.

Terminal-state enforcement: TERMINATED fabric elements must never transition back to active/suspended states.

Immutable historical records: History entries must never be modified, deleted, or reordered.

Snapshot rebuild consistency: Snapshots are non-authoritative caches and must be fully rebuildable from active source fabric routing data.

In-memory storage only: Zero database migrations.

No external integrations: Zero external routing middleware.

No breaking API changes: Keep all existing endpoints and routers backward compatible.

Full backward compatibility: Guarantee that all previous sprints (1-36) run without regression.

AI Advisory-only enforcement: Physically block the AI Security Copilot from executing any fabric modifications.

Lifecycle & Hardening Rules

Fabric Terminal State Rule

TERMINATED is a terminal state.

Requirements:

synchronization cannot reactivate TERMINATED fabric elements

worker refresh cycles cannot reactivate TERMINATED fabric elements

propagation updates cannot reactivate TERMINATED fabric elements

confidence scoring calculations cannot reactivate TERMINATED fabric elements

drift processing cannot reactivate TERMINATED fabric elements

snapshot rebuilds cannot reactivate TERMINATED fabric elements

A new fabric element may only be created if the fingerprint changes.

Fabric Identity Preservation Rule

If synchronization generates an identical fingerprint:

preserve fabric_id / node_id

preserve fingerprint

preserve created_at

preserve history

preserve confidence_weights

preserve target_links

Do not create duplicates.

Fabric History Preservation Rule

History entries are immutable.

Requirements:

never modify history

never delete history

never reorder history

History must survive:

worker refreshes

intelligence propagation

confidence scoring

drift processing

snapshot rebuilds

History is the authoritative audit trail. Only append new events.

Intelligence Propagation Determinism Rule

Fabric calculations are derived intelligence.

Requirements:

intelligence propagation schedules must be deterministic

confidence score distributions must be deterministic

cross-domain score maps must be deterministic

priority score weightings must be deterministic

Identical inputs must always produce identical outputs.

Calculations must never mutate:

fabric records

histories

target entities

snapshots

Calculations are read-only intelligence generation.

Intelligence Propagation Preservation Rule

Propagation mappings are authoritative fabric intelligence.

Requirements:

propagation recalculations must never modify:

source intelligence

target intelligence

histories

snapshots

confidence propagation calculations are read-only intelligence generation

propagation services may generate derived intelligence but may never overwrite authoritative intelligence

Source intelligence remains authoritative.

Fabric Snapshot Consistency Rule

Snapshots are:

cache-only

rebuildable

non-authoritative

If cache is:

missing

deleted

corrupted

generate_snapshot() and get_snapshot() must rebuild from source fabric state.No state may exist exclusively inside snapshots. Source fabric records remain authoritative.

Proposed Changes

Domain Models

[NEW] security_intelligence_fabric.py

Define enums:

FabricPriority (LOW, MEDIUM, HIGH, CRITICAL)

FabricStatus (ACTIVE, SUSPENDED, TERMINATED)

PropagationMode (DIRECT, WEIGHTED, CASCADING)

Define Pydantic models:

FabricIntelligenceNodeResponse: Represents a node in the intelligence fabric.

ConfidencePropagationResponse: Mapped route representing confidence and threat score propagation.

FabricCorrelationResponse: Extracted cross-domain scores.

FabricSnapshotResponse: Summarizes fabric throughput metrics.

FabricHistoryEntry: Audit logs.

Registries

[NEW] intelligence_source_registry.py

Pre-seeded sources: ASSET, RISK, GRC, POSTURE, RESILIENCE, KNOWLEDGE, THREAT_INTEL, INCIDENT, CASE.

[NEW] propagation_direction_registry.py

Pre-seeded directions: RISK_TO_DECISION, DECISION_TO_PLAN, THREAT_TO_KNOWLEDGE, POSTURE_TO_COMPLIANCE.

[NEW] confidence_weight_registry.py

Standardizes propagation confidence modifiers and decay factors.

Fingerprinting

[NEW] fabric_fingerprint_service.py

Generates SHA256(source_type + "_" + str(scope_id or "global") + "_" + rules_hash) stable fingerprint.

Core Services

[NEW] fabric_history_service.py

Immutable append-only history tracking FABRIC_CREATED, ROUTE_CREATED, PROPAGATED, SUSPENDED, TERMINATED.

[NEW] unified_security_intelligence_fabric_service.py

Coordinates fabric state, synchronization, lifecycle transitions, and duplicate prevention.

Enforces Fabric Terminal State Rule.

[NEW] intelligence_propagation_service.py

Performs deterministic cross-domain confidence and intelligence propagation calculations combining Sprints 33-36 outputs.

[NEW] fabric_drift_service.py

Detects score drift, confidence level variations, or propagation errors. Emits fabric.drift.

[NEW] fabric_snapshot_service.py

Cache-only snapshot rebuild engine from active fabric data.

Integrations

[MODIFY] worker.py

Add periodic background tasks for fabric intelligence propagation checks, score map validations, confidence drift analysis, and snapshot cache rebuilding.

Sprint 37 Worker Execution Order

UnifiedSecurityIntelligenceFabricService.sync_fabric_state()

IntelligencePropagationService.process_propagation()

FabricDriftService.process_drift()

FabricSnapshotService.generate_snapshot()

[MODIFY] ai_context_builder.py

Inject intelligence propagation summaries, fabric health metrics, and confidence score maps into AI contexts.

[MODIFY] ai_prompt_builder.py

Prompt guardrails blocking AI Copilot mutations to intelligence propagation paths, confidence weights, or fabric configurations.

[MODIFY] main.py

Register security_intelligence_fabric API router.

API Gateway

[NEW] security_intelligence_fabric.py

POST: /propagations, /score-maps, /fabric/{id}/terminate.

GET: /propagations, /score-maps, /drift, /summary.

Enforces RBAC and scope isolation.

Verification Plan

Automated Tests

Implement 110+ integration tests in test_security_intelligence_fabric.py.Coverage target: >= 85% code coverage.

Sprint 37 Mandatory Test Cases

test_fabric_auto_creation()

test_propagation_route_auto_creation()

test_fabric_fingerprint_stability()

test_fabric_identity_preservation()

test_fabric_duplicate_prevention()

test_fabric_suspend_transition()

test_fabric_terminate_transition()

test_fabric_terminal_state_enforcement()

test_terminated_fabric_not_reactivated_by_sync()

test_terminated_fabric_not_reactivated_by_worker()

test_terminated_fabric_not_reactivated_by_snapshot()

test_terminated_fabric_not_reactivated_by_drift()

test_terminated_fabric_not_reactivated_by_propagation()

test_fabric_history_preserved()

test_fabric_history_immutable()

test_fabric_history_order_preserved()

test_propagation_schedule_deterministic()

test_confidence_weight_consistency()

test_intelligence_propagation_impact()

test_fabric_drift_detection()

test_fabric_drift_clearing()

test_snapshot_rebuild_consistency()

test_snapshot_rebuild_after_cache_deletion()

test_snapshot_rebuild_after_cache_corruption()

test_snapshot_not_authoritative()

test_snapshot_rebuild_from_source_of_truth()

test_ai_context_fabric_injection()

test_ai_advisory_only_enforcement()

test_rbac_fabric_scope_validation()

test_worker_integration()

test_fabric_identity_preserved_after_worker_refresh()

test_fabric_identity_preserved_after_propagation_refresh()

test_fabric_identity_preserved_after_snapshot_rebuild()

test_fabric_identity_preserved_after_drift_processing()

test_propagation_determinism()

test_scope_isolation_for_fabric_events()

test_fabric_score_stability()

Run:

.venv\Scripts\pytest backend/tests/integration/test_security_intelligence_fabric.py
.venv\Scripts\pytest

Deliverables

1. Architecture Summary

Details of unified intelligence propagation, confidence decay metrics, propagation drift calculations, and snapshot caches.

2. File Manifest

List of all new and modified files.

3. Testing Results

Pytest verification outputs demonstrating zero regressions.

STOP.Wait for user approval before implementation.


One Tiny Optional Improvement

This is not a blocker.

In:

Architectural Constraints

you still have:

preserve unique fabric channel and node identifiers

The word:

channel

is leftover terminology from the earlier fabric draft.

I would replace:

fabric channel and node identifiers

with:

fabric propagation and node identifiers

or:

fabric route and node identifiers

to completely remove messaging-layer terminology.

This is purely cosmetic.


STOP.Wait for user approval before implementation.
