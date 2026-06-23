# Sprint 27 — Implementation Plan

> **Paste your implementation plan for Sprint 27 below this line.**
> Delete this placeholder text when adding your content.

# Sprint 27: Executive Risk & Board Reporting Intelligence

This sprint introduces **Executive Risk & Board Reporting Intelligence** to AegisX. It expands the platform to provide C-suite and Board stakeholders with deterministic, auditable, and snapshot-rebuildable executive reports, scorecards, cyber risk heatmaps, trends, and executive drift detection.

## Architectural Constraints (Sprint 1–26 Compliance)
- Registry-driven design
- Deterministic fingerprinting (`SHA256` hashing)
- Identity preservation
- Terminal-state enforcement (e.g. `ARCHIVED` is terminal and cannot be reactivated)
- Immutable history preservation
- Snapshot rebuild consistency
- In-memory storage only
- Full backward compatibility with Sprints 1–26
- AI Advisory-only enforcement

## Domain Models (`backend/src/domain/entities/executive_reporting.py`) [NEW]

Create a new file containing the required Pydantic models and Enums:
1. **`ExecutiveSeverity` (Enum):** `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
2. **`ExecutiveReportStatus` (Enum):** `DRAFT`, `GENERATED`, `PUBLISHED`, `ARCHIVED`
3. **`ScorecardStatus` (Enum):** `HEALTHY`, `WATCH`, `AT_RISK`, `CRITICAL`
4. **`ExecutiveReportResponse` (BaseModel):** Contains `report_id`, `report_fingerprint`, `title`, `description`, `report_period`, `status`, `overall_risk_score`, `program_score`, `scorecard_status`, `scope_id`, `created_at`, `updated_at`
5. **`ExecutiveScorecardResponse` (BaseModel):** Contains `scorecard_id`, `overall_health`, `risk_score`, `program_score`, `kpi_score`, `kri_score`, `coverage_score`, `trend_score`, `generated_at`
6. **`ExecutiveHistoryEntry` (BaseModel):** Contains `report_id`, `timestamp`, `event_type`, `details`

## Registries (`backend/src/services/`) [NEW]

1. **`executive_reporting_registry.py`**:
   - Pre-seeds report types: `BOARD_REPORT`, `EXECUTIVE_SUMMARY`, `RISK_REVIEW`, `QUARTERLY_REVIEW`, `MONTHLY_REVIEW`.
   - Validates supported report classifications.
2. **`scorecard_registry.py`**:
   - Defines deterministic status thresholds for scorecards (`HEALTHY`, `WATCH`, `AT_RISK`, `CRITICAL`).

## Fingerprinting (`backend/src/services/executive_report_fingerprint_service.py`) [NEW]

Generates deterministic SHA256 hashes of `report_period`, `scope_id`, and `included_entities`.
The fingerprint remains stable across score/KPI/KRI changes and rebuilds, and changes only when the reporting period, scope, or included entities change.

## Core Services (`backend/src/services/`) [NEW]

1. **`executive_history_service.py`**:
   - Manages append-only immutable history entries tracking `CREATED`, `GENERATED`, `PUBLISHED`, `ARCHIVED`, `SCORE_CHANGED`, `RISK_CHANGED`, `DRIFT_DETECTED`.
   - **Executive History Preservation Rule**:
     - History entries are immutable.
     - Never modify existing history entries.
     - Never delete history entries.
     - Never reorder history entries.
     - Publication events append-only.
     - Archival events append-only.
     - Score changes append-only.
     - Drift events append-only.
     - History must survive: report publication, report archival, scorecard recalculation, trend recalculation, worker refresh cycles, and snapshot rebuilds.
     - History is the authoritative audit trail and must never be reconstructed from report state.
2. **`executive_reporting_service.py`**:
   - Manages executive report generation, publication, archival, sync, and scorecard generation.
   - **Executive Report Terminal State Rule**:
     - `ARCHIVED` is a terminal state.
     - Synchronization cannot reactivate `ARCHIVED` reports.
     - Worker refresh cycles cannot reactivate `ARCHIVED` reports.
     - Scorecard recalculations cannot reactivate `ARCHIVED` reports.
     - Trend recalculations cannot reactivate `ARCHIVED` reports.
     - Drift processing cannot reactivate `ARCHIVED` reports.
     - Snapshot rebuilds cannot reactivate `ARCHIVED` reports.
     - A new Executive Report may only be created if the report fingerprint changes.
   - Preserves report identity (reuse `report_id` and `created_at` on identical fingerprints).
3. **`executive_scorecard_service.py`**:
   - Computes `overall_health` (composite score), `risk_score` (from `RiskIntelligenceService`), `program_score`, `kpi_score`, `kri_score`, `coverage_score`, and `trend_score`.
4. **`executive_heatmap_service.py`**:
   - Generates cyber risk heatmaps, severity distributions, program health maps, and coverage maps.
5. **`executive_trend_service.py`**:
   - Tracks risk, program, coverage, KPI, and KRI trends over time.
6. **`executive_drift_service.py`**:
   - Detects score and metric changes (`RISK_INCREASED`, `RISK_DECREASED`, `PROGRAM_SCORE_CHANGED`, `KPI_CHANGED`, `KRI_CHANGED`, `COVERAGE_CHANGED`).
   - Emits `executive.drift` and `executive.score_changed` workflow events.
7. **`executive_snapshot_service.py`**:
   - **Executive Snapshot Consistency Rule**:
     - Snapshots are cache-only, rebuildable, and non-authoritative.
     - If the cache is missing, deleted, or corrupted, then `generate_snapshot()` and `get_snapshot()` must rebuild from source executive intelligence.
     - No state may exist exclusively inside snapshots.

## Integrations [MODIFY]

1. **`backend/src/infrastructure/celery/worker.py`**:
   - Hook the following into the refresh loop, wrapped gracefully:
     - `ExecutiveReportingService.sync_reports()`
     - `ExecutiveScorecardService.calculate()`
     - `ExecutiveTrendService.calculate()`
     - `ExecutiveDriftService.process_drift()`
     - `ExecutiveSnapshotService.generate_snapshot()`
2. **`backend/src/services/ai_context_builder.py`**:
   - Inject `executive_summary`, `board_summary`, `executive_scorecard`, `risk_heatmap`, `trend_summary`, and `executive_risk_score` into the executive context, program context, and board context.
3. **`backend/src/services/ai_prompt_builder.py`**:
   - Add prompt constraints to prevent the AI Security Copilot from performing executive reporting mutations (creating reports, publishing reports, archiving reports, modifying scorecards, or altering risk/KPI/KRI values).
4. **`backend/src/api/v1/routers/executive_reporting.py`**:
   - Implement REST endpoints for reports, scorecards, heatmaps, trends, drift, and executive summary.
   - Enforce RBAC (admin/operator write permissions, reader read permissions) and scope-level resource filtering.
5. **`backend/src/main.py`**:
   - Import and register the new executive reporting router.

## Verification Plan

Create `backend/tests/integration/test_executive_reporting.py` to run **90+ integration tests** achieving **>= 85% coverage** on all new services.

### Automated Tests
I will implement 90+ tests, including:
1. `test_report_auto_creation()`
2. `test_report_fingerprint_stability()`
3. `test_report_generate_transition()`
4. `test_report_publish_transition()`
5. `test_report_archive_transition()`
6. `test_report_terminal_state_enforcement()`
7. `test_report_sync_preserves_identity()`
8. `test_report_duplicate_prevention()`
9. `test_report_history_preserved()`
10. `test_report_history_immutable()`
11. `test_scorecard_generation()`
12. `test_scorecard_deterministic()`
13. `test_heatmap_generation()`
14. `test_trend_generation()`
15. `test_risk_trend_detection()`
16. `test_program_trend_detection()`
17. `test_kpi_trend_detection()`
18. `test_kri_trend_detection()`
19. `test_executive_drift_detection()`
20. `test_snapshot_rebuild_consistency()`
21. `test_snapshot_rebuild_after_cache_deletion()`
22. `test_snapshot_rebuild_after_cache_corruption()`
23. `test_snapshot_not_authoritative()`
24. `test_snapshot_rebuild_from_source_of_truth()`
25. `test_report_identity_preserved_after_publish()`
26. `test_report_identity_preserved_after_archive()`
27. `test_archived_report_not_reactivated_by_sync()`
28. `test_archived_report_not_reactivated_by_worker()`
29. `test_archived_report_not_reactivated_by_snapshot()`
30. `test_archived_report_not_reactivated_by_drift()`
31. `test_archived_report_not_reactivated_by_scorecard_refresh()`
32. `test_archived_report_not_reactivated_by_trend_refresh()`
33. `test_report_history_survives_snapshot_rebuild()`
34. `test_report_correlation_append_only()`
35. `test_report_identity_preserved_after_scorecard_recalculation()`
36. `test_report_identity_preserved_after_trend_recalculation()`
37. `test_report_score_stability()`
38. `test_report_heatmap_deterministic()`
39. `test_report_trend_persistence()`
40. `test_report_snapshot_not_authoritative()`
41. `test_report_history_order_preserved()`
42. `test_report_history_never_rewritten()`
43. `test_scorecard_status_thresholds()`
44. `test_heatmap_consistency()`
45. `test_heatmap_rebuild_consistency()`
46. `test_trend_calculation_deterministic()`
47. `test_scope_isolation_between_reports()`
48. `test_scope_isolation_between_scorecards()`
49. `test_scope_isolation_between_heatmaps()`
50. `test_scope_isolation_between_trends()`
51. `test_report_fingerprint_changes_on_period_change()`
52. `test_report_fingerprint_changes_on_scope_change()`
53. `test_report_fingerprint_changes_on_entity_change()`
54. `test_report_fingerprint_not_changed_by_score_updates()`
55. `test_report_fingerprint_not_changed_by_trend_updates()`
56. `test_ai_context_executive_injection()`
57. `test_ai_advisory_only_enforcement()`
58. `test_rbac_executive_scope_validation()`
59. `test_scorecard_registry_validation()`
60. `test_worker_integration()`
61. 30+ additional tests verifying reporting periods, risk distributions, scope isolation, history copying, trend persistence, correlation persistence, etc.


