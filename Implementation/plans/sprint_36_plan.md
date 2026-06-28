Implementation Plan - Sprint 36: Autonomous Security Planning Intelligence

Transform AegisX from a Security Decision Intelligence Platform into an Autonomous Security Planning Intelligence Platform.

User Review Required

[!IMPORTANT]

All plans, roadmaps, optimization criteria, milestone logs, plan histories, and snapshots operate strictly in-memory.

Zero database migrations.

Zero external project management integrations.

Zero external planning systems.

AI Security Copilot remains strictly advisory-only and cannot approve or modify plan milestones or priority assignments.

Architectural Constraints (Sprint 1–36 Compliance)

Registry-driven design: All plan categories, priority tiers, roadmap segments, and milestone objectives must be validated against registries.

Deterministic fingerprinting: Planning fingerprints must be generated using SHA-256 and remain stable.

Identity preservation: Syncs and updates must preserve unique planning record identifiers.

Terminal-state enforcement: CLOSED plans must never transition back to draft/active states.

Immutable historical records: History entries must never be modified, deleted, or reordered.

Snapshot rebuild consistency: Snapshots are non-authoritative caches and must be fully rebuildable from active source planning data.

In-memory storage only: Zero database migrations.

No external integrations: Zero external planning trackers.

No breaking API changes: Keep all existing endpoints and routers backward compatible.

Full backward compatibility: Guarantee that all previous sprints (1-35) run without regression.

AI Advisory-only enforcement: Physically block the AI Security Copilot from executing any planning mutations.

Lifecycle & Hardening Rules

Planning Terminal State Rule

CLOSED is a terminal state.

Requirements:

synchronization cannot reactivate CLOSED plans

worker refresh cycles cannot reactivate CLOSED plans

milestone mapping updates cannot reactivate CLOSED plans

optimization calculations cannot reactivate CLOSED plans

drift processing cannot reactivate CLOSED plans

snapshot rebuilds cannot reactivate CLOSED plans

A new plan may only be created if the fingerprint changes.

Plan Approval Constraint Rule

The APPROVED status does not imply AI approval.

Requirements:

Plan approvals must always be triggered via explicit external actions (e.g., manual API router calls)

The AI Security Copilot remains strictly advisory-only and cannot change a plan's status to APPROVED or validate plan execution roadmaps

Planning Identity Preservation Rule

If synchronization generates an identical fingerprint:

preserve plan_id

preserve fingerprint

preserve created_at

preserve history

preserve milestones

preserve priorities

Do not create duplicate plans.

Planning History Preservation Rule

History entries are immutable.

Requirements:

never modify history

never delete history

never reorder history

History must survive:

worker refreshes

optimization scoring

milestone updates

drift processing

snapshot rebuilds

History is the authoritative audit trail. Only append new events.

Planning Optimization Determinism Rule

Planning calculations are derived intelligence.

Requirements:

milestone optimization sequencing must be deterministic

planning priorities must be deterministic

resource availability allocation calculations must be deterministic

scheduling parameters must be deterministic

Identical inputs must always produce identical outputs.

Calculations must never mutate:

plan records

histories

milestones

snapshots

Calculations are read-only intelligence generation.

Planning Snapshot Consistency Rule

Snapshots are:

cache-only

rebuildable

non-authoritative

If cache is:

missing

deleted

corrupted

generate_snapshot() and get_snapshot() must rebuild from source planning recommendations.No state may exist exclusively inside snapshots. Source plan records remain authoritative.

Proposed Changes

Domain Models

[NEW] autonomous_planning.py

Define enums:

PlanPriority (LOW, MEDIUM, HIGH, CRITICAL)

PlanStatus (DRAFT, APPROVED, ACTIVE, CLOSED)

MilestoneType (REMEDIATION, VALIDATION, DEPLOYMENT, AUDIT)

Define Pydantic models:

PlanningRecordResponse: Represents an autonomous security plan.

MilestoneResponse: Represents milestones in the plan.

RoadmapResponse: Represents the optimized order of milestones.

PlanningSnapshotResponse: Summarizes planning progress metrics.

PlanningHistoryEntry: Audit logs.

Registries

[NEW] planning_category_registry.py

Pre-seeded: IMMEDIATE_THREAT_CONTAINMENT, COMPLIANCE_ALIGNMENT, RISK_REDUCTION_CAMPAIGN, POSTURE_HARDENING.

[NEW] planning_priority_registry.py

Maps milestone types to weight coefficients.

[NEW] milestone_type_registry.py

Pre-seeded: REMEDIATION, VALIDATION, DEPLOYMENT, AUDIT.

Fingerprinting

[NEW] planning_fingerprint_service.py

Generates SHA256(category + "_" + str(scope_id or "global") + "_" + name.strip().lower()) stable fingerprint.

Core Services

[NEW] planning_history_service.py

Immutable append-only history tracking CREATED, APPROVED, ACTIVATED, MILESTONE_UPDATED, DRIFT_DETECTED, CLOSED.

[NEW] autonomous_security_planning_service.py

Handles planning creation, synchronization, approvals, and duplicate checks.

Enforces Planning Terminal State Rule.

[NEW] planning_optimization_service.py

Sequences milestones deterministically based on Sprint 35 Decision matrix data.

[NEW] planning_drift_service.py

Detects schedule drifts, delays, or cost changes. Emits planning.drift and planning.milestone_changed.

[NEW] planning_snapshot_service.py

Cache-only snapshot rebuild engine from active planning data.

Integrations

[MODIFY] worker.py

Add periodic background tasks for planning builds, optimization schedules, milestone delay tracking, and planning snapshot generation.

Sprint 36 Worker Execution Order

AutonomousSecurityPlanningService.sync_plans()

PlanningOptimizationService.optimize_sequences()

PlanningDriftService.process_drift()

PlanningSnapshotService.generate_snapshot()

[MODIFY] ai_context_builder.py

Inject planning roadmaps, milestones, prioritizations, and delay drifts into AI contexts.

[MODIFY] ai_prompt_builder.py

Prompt guardrails blocking AI Copilot mutations to milestones, roadmaps, or priority classifications.

[MODIFY] main.py

Register autonomous_planning API router.

API Gateway

[NEW] autonomous_planning.py

POST: /, /{id}/approve, /{id}/activate, /{id}/close.

GET: /, /active, /roadmaps, /drift, /summary, /{id}.

Enforces RBAC and scope isolation.

Verification Plan

Automated Tests

Implement 110+ integration tests in test_autonomous_planning.py.Coverage target: >= 85% code coverage.

Sprint 36 Mandatory Test Cases

test_plan_auto_creation()

test_plan_fingerprint_stability()

test_plan_identity_preservation()

test_plan_duplicate_prevention()

test_plan_approve_transition()

test_plan_activate_transition()

test_plan_close_transition()

test_plan_terminal_state_enforcement()

test_closed_plan_not_reactivated_by_sync()

test_closed_plan_not_reactivated_by_worker()

test_closed_plan_not_reactivated_by_snapshot()

test_closed_plan_not_reactivated_by_drift()

test_closed_plan_not_reactivated_by_optimization()

test_planning_history_preserved()

test_planning_history_immutable()

test_planning_history_order_preserved()

test_optimization_sequencing_deterministic()

test_priority_calculation_consistency()

test_milestone_completion_impact()

test_planning_drift_detection()

test_planning_drift_clearing()

test_snapshot_rebuild_consistency()

test_snapshot_rebuild_after_cache_deletion()

test_snapshot_rebuild_after_cache_corruption()

test_snapshot_not_authoritative()

test_snapshot_rebuild_from_source_of_truth()

test_ai_context_planning_injection()

test_ai_advisory_only_enforcement()

test_rbac_planning_scope_validation()

test_worker_integration()

test_planning_identity_preserved_after_worker_refresh()

test_planning_identity_preserved_after_optimization_refresh()

test_planning_identity_preserved_after_snapshot_rebuild()

test_planning_identity_preserved_after_drift_processing()

test_optimization_sequence_determinism()

test_scope_isolation_for_plans()

test_planning_score_stability()

Run:

.venv\Scripts\pytest backend/tests/integration/test_autonomous_planning.py
.venv\Scripts\pytest

Deliverables

1. Architecture Summary

Details of autonomous security plans, optimization algorithms, milestone sequencing, drift detection, and cached rebuild engines.

2. File Manifest

List of all new and modified files.

3. Testing Results

Pytest verification outputs demonstrating zero regressions.

STOP.Wait for user approval before implementation.