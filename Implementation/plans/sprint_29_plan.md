# Sprint 29 — Implementation Plan

> **Paste your implementation plan for Sprint 29 below this line.**
> Delete this placeholder text when adding your content.

Implementation Plan - Sprint 29: Security Operations Analytics Intelligence

This plan details the implementation of Sprint 29 to transition AegisX into a Security Operations Analytics Intelligence Platform. This is registry-driven, offline-capable, in-memory, deterministic, and fully backward compatible with Sprints 1–28.

User Review Required

[!IMPORTANT]Analytics Lifecycle: ACTIVE → REVIEW → COMPLETED → ARCHIVED.ARCHIVED is a terminal state. Once archived, an analytics record is locked and cannot be mutated or reactivated by any synchronization, worker, KPI/KRI calculations, drift checks, or snapshot rebuilds.

[!IMPORTANT]Security Operations Analytics Completion Rule:COMPLETED behaves as a protected state.

COMPLETED analytics may continue to be viewed, reported, correlated, and scored.

Synchronization cannot move COMPLETED back to ACTIVE.

Worker refreshes cannot move COMPLETED back to ACTIVE.

KPI recalculations cannot move COMPLETED back to ACTIVE.

KRI recalculations cannot move COMPLETED back to ACTIVE.This prevents lifecycle regression before ARCHIVED.

[!IMPORTANT]Security Operations Analytics History Preservation Rule:History entries are immutable:

Never modify existing entries.

Never delete entries.

Never reorder entries.

KPI, KRI, Score changes, and Drift events are append-only.

History must survive worker refresh cycles, KPI/KRI recalculations, drift processing, and snapshot rebuilds.

History is the authoritative audit trail and must never be reconstructed from analytics state.

[!IMPORTANT]Security Operations Snapshot Consistency Rule:Snapshots are cache-only, rebuildable, and non-authoritative:

If a snapshot is missing, deleted, or corrupted, the snapshot service must rebuild from source analytics intelligence.

No operational state may exist exclusively inside snapshots.

Snapshots must never be treated as the system of record.

This mirrors the Executive Snapshot, Program Snapshot, Cyber Resilience Snapshot, and Security Posture Snapshot Rules.

[!IMPORTANT]Advisory AI Prompts:The AI Security Copilot will be strictly advisory-only and physically blocked from mutating security operations analytics (creating analytics, archiving analytics, modifying KPIs/KRIs, modifying analyst scores, or modifying queue metrics).

Open Questions

None. The specifications are clear, follow established AegisX patterns, and preserve full backward compatibility.

Proposed Changes

Domain Model

[NEW] security_operations_analytics.py

Contains:

Enums:

AnalyticsSeverity (LOW, MEDIUM, HIGH, CRITICAL)

AnalyticsStatus (ACTIVE, REVIEW, COMPLETED, ARCHIVED)

KPIStatus (ON_TARGET, AT_RISK, OFF_TARGET)

KRIStatus (LOW_RISK, MEDIUM_RISK, HIGH_RISK, CRITICAL_RISK)

Pydantic Response Models:

AnalyticsResponse: analytics_id, analytics_fingerprint, analytics_name, description, status, scope_id, created_at, updated_at

AnalystPerformanceResponse: analyst_id, analyst_name, alerts_handled, incidents_handled, cases_handled, average_response_time, average_resolution_time, analyst_score

OperationalKPIResponse: kpi_id, kpi_name, current_value, target_value, status, calculated_at

OperationalKRIResponse: kri_id, kri_name, current_value, threshold_value, status, calculated_at

AnalyticsHistoryEntry: analytics_id, timestamp, event_type, details

Registries

[NEW] soc_kpi_registry.py

Pre-seeded KPIs:

Mean Time To Detect (MTTD)

Mean Time To Respond (MTTR)

Mean Time To Contain (MTTC)

Mean Time To Resolve (MTTR (resolve))

Alert Closure Rate

Case Closure Rate

Incident Closure Rate

Analyst Utilization

Queue Processing Rate

Provides validation and config mapping.

[NEW] soc_kri_registry.py

Pre-seeded KRIs:

Alert Backlog Growth

Incident Backlog Growth

Case Backlog Growth

Escalation Growth

SLA Breach Growth

Critical Alert Growth

Provides validation and thresholds mapping.

[NEW] analyst_role_registry.py

Pre-seeded analyst roles:

TIER1_ANALYST

TIER2_ANALYST

TIER3_ANALYST

INCIDENT_RESPONDER

THREAT_HUNTER

SOC_MANAGER

Provides validation and list methods.

Fingerprinting & History

[NEW] analytics_fingerprint_service.py

Generates: SHA256(normalized_analytics_name, scope_id).Stable across KPI/KRI changes, recalculations, drift, and snapshot runs.

[NEW] analytics_history_service.py

Append-only history store. Returns deep-copied entries to guarantee immutability.Tracks: CREATED, KPI_CHANGED, KRI_CHANGED, SCORE_CHANGED, DRIFT_DETECTED, REVIEWED, ARCHIVED.

Core Analytics Services

[NEW] security_operations_analytics_service.py

Handles:

Creating analytics and synchronization.

Transitioning status: forward transitions only. Enforces that ARCHIVED is terminal and cannot be reopened or mutated. Enforces that COMPLETED cannot regress back to ACTIVE.

Sync checks that active scopes generate corresponding analytics.

[NEW] analyst_performance_service.py

Deterministic calculations of:

Handle counts (alerts, incidents, cases handled).

Averages (Mean response/resolution times).

Score calculation (analyst_score from 0-100 based on efficiency metrics).

Workload and analyst rankings.

[NEW] queue_analytics_service.py

Calculates:

Queue sizes, processing efficiency, backlog metrics.

[NEW] operational_kpi_service.py

Calculates:

MTTD, MTTR, MTTC, MTTR (resolve) and utilization indicators.

[NEW] operational_kri_service.py

Calculates:

Backlog growth and SLA breach indicators.

[NEW] soc_drift_service.py

Compares values against baseline targets, emitting soc.drift and soc.performance_changed events.

[NEW] soc_snapshot_service.py

Cache-only in-memory snapshots.Auto-rebuilds from core services when cache is deleted or missing.

Integrations

[MODIFY] worker.py

Modify worker calculations to run Sprint 29 analytics after Sprint 28:

try:
    from src.services.security_operations_analytics_service import SecurityOperationsAnalyticsService
    from src.services.analyst_performance_service import AnalystPerformanceService
    from src.services.operational_kpi_service import OperationalKPIService
    from src.services.operational_kri_service import OperationalKRIService
    from src.services.soc_drift_service import SOCDriftService
    from src.services.soc_snapshot_service import SOCSnapshotService

    await SecurityOperationsAnalyticsService.sync_analytics(db)
    AnalystPerformanceService.calculate()
    OperationalKPIService.calculate()
    OperationalKRIService.calculate()
    SOCDriftService.process_drift()
    SOCSnapshotService.generate_snapshot(scope_id)
except Exception as soc_err:
    import logging
    logging.error(f"Failed to perform SOC analytics intelligence checks: {soc_err}")

[MODIFY] ai_context_builder.py

Inject the following metrics into build_asset_context, build_finding_context, build_incident_context, build_case_context, build_executive_context, and program/resilience blocks:

analyst_performance_summary

queue_analytics_summary

operational_kpis

operational_kris

operational_health_score

soc_drift_summary

[MODIFY] ai_prompt_builder.py

Append constraint string in all prompt methods:

physically blocked from security operations analytics mutations (creating analytics, archiving analytics, modifying KPIs, modifying KRIs, modifying analyst scores, or modifying queue metrics)

API Router & Gateway

[NEW] security_operations_analytics.py (Router)

Endpoints:

GET / — List analytics

GET /analytics/{id} — Get single analytics

GET /analytics/active — Active analytics

GET /analytics/archived — Archived analytics

GET /analysts — List analysts

GET /analysts/rankings — Analyst performance rankings

GET /queues — Queue metrics

GET /queues/backlog — Backlog metrics

GET /kpis — KPI metrics

GET /kris — KRI metrics

GET /drift — Drift metrics

GET /summary — Snapshots dashboard

POST /analytics — Create analytics record

POST /analytics/{id}/review — Transition to REVIEW

POST /analytics/{id}/archive — Transition to ARCHIVED

Enforces RBAC and scope filtering.

[MODIFY] main.py

Register router:app.include_router(security_operations_analytics_router, prefix=settings.API_V1_STR + "/security-operations-analytics")

Verification Plan

Automated Tests

Run Sprint 29 integration tests:.venv\Scripts\pytest backend/tests/integration/test_security_operations_analytics.py -v

Run regression tests:.venv\Scripts\pytest backend/tests/integration/

Additional Mandatory Integration Tests

We will add the following specific tests to the test suite to satisfy the mandatory requirements:

test_completed_analytics_not_reactivated_by_sync()

test_completed_analytics_not_reactivated_by_worker()

test_completed_analytics_not_reactivated_by_kpi_refresh()

test_completed_analytics_not_reactivated_by_kri_refresh()

test_analyst_ranking_stability()

test_queue_metrics_deterministic()

test_snapshot_identity_preserved_after_rebuild()

test_analytics_history_survives_worker_refresh()