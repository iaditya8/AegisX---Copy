# Sprint 28 — Implementation Plan

> **Paste your implementation plan for Sprint 28 below this line.**
> Delete this placeholder text when adding your content.

Sprint 28: Cyber Resilience Intelligence

Transform AegisX from an Executive Risk & Board Reporting Intelligence Platform into a Cyber Resilience Intelligence Platform.

User Review Required

[!IMPORTANT]Resilience Lifecycle: PLANNED → ACTIVE → UNDER_REVIEW → VALIDATED → COMPLETED → CLOSED. Both COMPLETED and CLOSED are terminal states (mirrors Sprint 27's ARCHIVED terminal pattern, but with two terminal states instead of one).

[!IMPORTANT]Recovery Objective Model: Each resilience record can have multiple RecoveryObjective entries (RTO/RPO). Compliance is calculated as min(target, current) / target * 100. Objectives are keyed by (resilience_id, objective_type) so each record has at most one RTO and one RPO.

[!IMPORTANT]Resilience Scoring Architecture: Three independent scores calculated from source data:

resilience_score = weighted average of recovery readiness (30%), objective compliance (30%), service criticality factor (20%), validation completion rate (20%)

readiness_score = recovery plan coverage (40%), validation coverage (30%), resilience testing status (30%)

recovery_confidence_score = objective compliance (40%), validation history depth (30%), readiness state (30%)

All three are deterministic given identical source data.

[!IMPORTANT]Allowed Lifecycle Transitions: Forward-only transitions enforced via a transition map. COMPLETED and CLOSED have empty transition sets (terminal). PLANNED can go to ACTIVE. ACTIVE to UNDER_REVIEW, VALIDATED, COMPLETED, or CLOSED. UNDER_REVIEW to VALIDATED, COMPLETED, or CLOSED. VALIDATED to COMPLETED or CLOSED.

Open Questions

None — all design decisions are resolved by following Sprint 27 patterns with the specified enumerations and scoring formulas.

Proposed Changes

Domain Model

[NEW] cyber_resilience.py

4 Enums + 3 Pydantic response models:

Enum

Values

ResilienceSeverity

LOW, MEDIUM, HIGH, CRITICAL

ResilienceStatus

PLANNED, ACTIVE, UNDER_REVIEW, VALIDATED, COMPLETED, CLOSED

RecoveryObjectiveType

RTO, RPO

ServiceCriticality

LOW, MEDIUM, HIGH, MISSION_CRITICAL

Model

Key Fields

CyberResilienceResponse

resilience_id, resilience_fingerprint, title, description, service_name, service_criticality, resilience_score, readiness_score, recovery_confidence_score, status, scope_id, created_at, updated_at

RecoveryObjectiveResponse

objective_id, objective_type, target_value, current_value, compliance_percentage, created_at, updated_at

ResilienceHistoryEntry

resilience_id, timestamp, event_type, details

Registries

[NEW] resilience_registry.py

Pre-seeded categories: BUSINESS_CONTINUITY, DISASTER_RECOVERY, RECOVERY_VALIDATION, RECOVERY_READINESS, SERVICE_RESILIENCE. Provides validate() and list_types().

[NEW] criticality_registry.py

Pre-seeded: LOW, MEDIUM, HIGH, MISSION_CRITICAL. Provides deterministic criticality weight factors for scoring (LOW=1.0, MEDIUM=1.5, HIGH=2.0, MISSION_CRITICAL=3.0).

[NEW] recovery_objective_registry.py

Pre-seeded standard tiers:

RTO: 15min, 1h, 4h, 24h

RPO: 0min, 15min, 1h, 24h

Provides validate(), get_tiers(), list_types().

Fingerprinting

[NEW] resilience_fingerprint_service.py

SHA256(normalized_title + service_name + service_criticality). Stable across score/readiness/confidence/drift/snapshot changes. Changes only when title, service_name, or criticality change. Follows executive_report_fingerprint_service.py pattern.

Core Services

[NEW] resilience_history_service.py

Immutable append-only history following executive_history_service.py pattern. Deep-copy on read. Tracks: CREATED, ACTIVATED, VALIDATED, COMPLETED, CLOSED, READINESS_CHANGED, RECOVERY_CHANGED, DRIFT_DETECTED.

[NEW] cyber_resilience_service.py

Core service following executive_reporting_service.py pattern:

create_resilience() — fingerprint-based dedup, identity preservation

transition_status() — forward-only, terminal state enforcement for COMPLETED/CLOSED

get_resilience(), get_all_resilience(), get_active(), get_completed()

sync_resilience(db) — async, creates records from scope data, never reactivates terminal records

clear_resilience() — test cleanup

Allowed transitions:

ALLOWED_TRANSITIONS = {
    "PLANNED": {"ACTIVE"},
    "ACTIVE": {"UNDER_REVIEW", "VALIDATED", "COMPLETED", "CLOSED"},
    "UNDER_REVIEW": {"VALIDATED", "COMPLETED", "CLOSED"},
    "VALIDATED": {"COMPLETED", "CLOSED"},
    "COMPLETED": set(),  # Terminal
    "CLOSED": set(),     # Terminal
}

[NEW] recovery_objective_service.py

Manages RTO/RPO objectives per resilience record:

set_objective(resilience_id, obj_type, target_value, current_value)

get_objectives(resilience_id)

calculate_compliance(resilience_id) — min(target, current) / target * 100

clear_objectives()

[NEW] resilience_scoring_service.py

Three deterministic scores:

calculate_resilience_score(resilience_id) — weighted: readiness 30%, objective compliance 30%, criticality factor 20%, validation rate 20%

calculate_readiness_score(resilience_id) — weighted: plan coverage 40%, validation coverage 30%, testing status 30%

calculate_recovery_confidence_score(resilience_id) — weighted: objective compliance 40%, validation depth 30%, readiness state 30%

calculate() — batch recalculates all non-terminal records

clear_scores()

[NEW] service_resilience_service.py

Computes:

get_service_resilience() — resilience metrics per service

get_critical_services() — filters MISSION_CRITICAL / HIGH criticality

get_resilience_distribution() — status counts breakdown

get_resilience_by_scope(scope_id) — scope-filtered records

[!IMPORTANT]Service Resilience Preservation Rule — Service-level resilience metrics are derived intelligence. Requirements:

Service resilience calculations must never modify resilience records

Service resilience calculations must never modify recovery objectives

Service resilience calculations must never modify resilience history

Service resilience calculations must never modify snapshots

Calculations are read-only and deterministic

This mirrors the Program Health Rule, Executive Scorecard Rule, and Risk Intelligence Rule — preventing derived analytics from becoming a source of truth.

[NEW] resilience_drift_service.py

Follows executive_drift_service.py pattern. Detects: READINESS_INCREASED, READINESS_DECREASED, RESILIENCE_SCORE_CHANGED, RECOVERY_CONFIDENCE_CHANGED, OBJECTIVE_COMPLIANCE_CHANGED. Emits resilience.drift and resilience.score_changed workflow events. Records history on non-terminal records only.

[NEW] cyber_resilience_snapshot_service.py

Follows executive_snapshot_service.py pattern. Cache-only, rebuildable. Computes: total_resilience_records, active_resilience_records, completed_resilience_records, resilience_score, readiness_score, recovery_confidence_score, critical_service_resilience, objective_compliance. Auto-rebuilds from source on cache miss/corruption.

Integrations

[MODIFY] worker.py

After Sprint 27 executive reporting block (~line 891), add a new Sprint 28 block:

# Cyber Resilience Intelligence (Sprint 28)
# Failures must never crash Celery
try:
    from src.services.cyber_resilience_service import CyberResilienceService
    from src.services.recovery_objective_service import RecoveryObjectiveService
    from src.services.resilience_scoring_service import ResilienceScoringService
    from src.services.resilience_drift_service import ResilienceDriftService
    from src.services.cyber_resilience_snapshot_service import CyberResilienceSnapshotService

    await CyberResilienceService.sync_resilience(db)
    RecoveryObjectiveService.calculate()
    ResilienceScoringService.calculate()
    ResilienceDriftService.process_drift()
    CyberResilienceSnapshotService.generate_snapshot(scope_id)
except Exception as res_err:
    import logging
    logging.error(f"Failed to perform cyber resilience intelligence checks: {res_err}")

[MODIFY] ai_context_builder.py

Add _build_cyber_resilience_context_block(scope_id) method. Inject into the executive context build_executive_context() after the Sprint 27 executive reporting block. Returns:

{
    "resilience_summary": "...",
    "resilience_score": float,
    "readiness_score": float,
    "recovery_confidence_score": float,
    "critical_services": [...],
    "recovery_objectives": [...]
}

[MODIFY] ai_prompt_builder.py

Append to the advisory-only constraints in all 4 prompt methods (build_asset_prompt, build_finding_prompt, build_executive_prompt, build_case_prompt):

physically blocked from cyber resilience mutations (creating resilience records, modifying resilience records, changing recovery objectives, altering resilience scores, validating resilience programs, completing resilience programs, closing resilience programs)

API Gateway

[NEW] cyber_resilience.py

Following executive_reporting.py router pattern:

Method

Path

Roles

GET

/

admin, operator, reader

GET

/active

admin, operator, reader

GET

/completed

admin, operator, reader

GET

/critical-services

admin, operator, reader

GET

/objectives

admin, operator, reader

GET

/drift

admin

GET

/summary

admin, operator, reader

POST

/

admin, operator

POST

/{id}/activate

admin, operator

POST

/{id}/validate

admin, operator

POST

/{id}/complete

admin, operator

POST

/{id}/close

admin, operator

All endpoints use RBAC, scope filtering, and StandardResponse wrappers.

[MODIFY] main.py

Register: app.include_router(cyber_resilience_router, prefix=settings.API_V1_STR + "/cyber-resilience")

Integration Tests

[NEW] test_cyber_resilience.py

100+ tests organized in 7 parts:

Part

Tests

Coverage

1: Registry & Fingerprint

15

Registries, enum values, fingerprint stability/change

2: Lifecycle & Identity

20

Creation, transitions, terminal states, identity preservation, duplicate prevention

3: History & Audit

15

Immutability, ordering, audit logs, workflow events

4: Scoring & Objectives

15

RTO/RPO, compliance, 3 scores, determinism

5: Snapshot, Drift & Service

15

Rebuild, corruption, drift detection, critical services, distribution

6: Integration & RBAC

15+

AI context, advisory enforcement, RBAC, worker, scope isolation

7: Service Resilience Preservation

5

Read-only enforcement, determinism, history/objective safety, scope isolation

All 55 mandatory tests plus 5 service resilience preservation tests plus 40+ additional coverage tests.

Part 7 — Service Resilience Preservation Tests:

test_service_resilience_read_only() — verify calculations don't modify resilience records

test_service_resilience_deterministic() — identical inputs produce identical outputs

test_service_resilience_does_not_modify_history() — history unchanged before/after calculation

test_service_resilience_does_not_modify_objectives() — objectives unchanged before/after calculation

test_service_resilience_scope_isolation() — scope-filtered results don't leak across scopes

Verification Plan

Automated Tests

.venv\Scripts\pytest backend/tests/integration/test_cyber_resilience.py -v
.venv\Scripts\pytest backend/tests/integration/ --tb=short -q

Manual Verification

Fingerprint stability across score/readiness/confidence recalculations

Terminal state enforcement: COMPLETED and CLOSED block all reactivation paths

History immutability: deep-copy isolation, append-only

Snapshot rebuild: cache deletion/corruption triggers auto-rebuild from source

Full regression: 998+ existing tests remain passing