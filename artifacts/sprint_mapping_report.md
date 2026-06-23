# Sprint Mapping Report

This report maps the 18 modified files and 149 untracked files currently residing in the working tree into logical commit groups corresponding to their architectural sprints.

## 1. Core Modifications (Sprints 1-4 Adjustments)
Files modified to support upcoming features (schema expansions, celery orchestration improvements):
- `Implementation/SprintReview.md`
- `backend/alembic/versions/rev_001_core_and_auth.py`
- `backend/create_user.py`
- `backend/src/main.py`
- `backend/src/infrastructure/database/models.py`
- `backend/src/infrastructure/celery/worker.py`
- `backend/src/api/v1/routers/scan_runs.py`
- `backend/src/api/v1/routers/workflows.py`
- `backend/src/domain/entities/asset.py`
- `backend/src/domain/entities/scope.py`
- `backend/src/services/asset_service.py`
- `backend/src/services/audit_service.py`
- `backend/src/services/scope_service.py`
- `backend/src/services/workflow_service.py`
- `backend/tests/integration/test_assets.py`
- `backend/tests/integration/test_auth.py`
- `backend/tests/integration/test_scopes.py`
- `backend/tests/integration/test_workflows.py`

## 2. Sprint 5: Plugin Architecture
- `backend/src/api/v1/routers/plugins.py`
- `backend/src/domain/entities/plugin.py`
- `backend/src/services/plugin_service.py`
- `backend/src/plugins/base.py`
- `backend/src/plugins/executor.py`
- `backend/src/plugins/host.py`
- `backend/src/plugins/mock_plugin.py`
- `backend/src/plugins/amass.py`
- `backend/src/plugins/assetfinder.py`
- `backend/src/plugins/naabu.py`
- `backend/src/plugins/nmap.py`
- `backend/src/plugins/nuclei.py`
- `backend/src/plugins/subfinder.py`
- `backend/src/plugins/theharvester.py`
- `backend/tests/integration/test_plugins.py`

## 3. Sprint 6: Recon & Service Discovery
- `backend/src/services/port_service.py`
- `backend/src/services/service_service.py`
- `backend/src/services/service_confidence_rules.py`
- `backend/src/services/service_normalization_service.py`
- `backend/src/services/discovery_normalization_service.py`
- `backend/tests/integration/test_recon_plugins.py`
- `backend/tests/integration/test_service_discovery.py`

## 4. Sprint 7: Asset Intelligence & History
- `backend/src/services/asset_intelligence_service.py`
- `backend/src/services/asset_criticality_service.py`
- `backend/src/services/asset_exposure_service.py`
- `backend/src/services/criticality_factor_registry.py`
- `backend/src/services/asset_risk_snapshot_service.py`

## 5. Sprint 8: Vulnerability Management
- `backend/alembic/versions/rev_002_findings_sprint8.py`
- `backend/src/api/v1/routers/findings.py`
- `backend/src/domain/entities/finding.py`
- `backend/src/services/finding_evidence_service.py`
- `backend/src/services/finding_fingerprint_service.py`
- `backend/src/services/finding_normalization_service.py`
- `backend/src/services/finding_reconciliation_service.py`
- `backend/src/services/finding_service.py`
- `backend/src/services/finding_severity_rules.py`
- `backend/src/services/finding_snapshot_service.py`
- `backend/src/services/template_tracking_service.py`
- `backend/tests/integration/test_findings.py`

## 6. Sprint 9: Correlation & Risk Intelligence
- `backend/src/api/v1/routers/correlations.py`
- `backend/src/domain/entities/correlation.py`
- `backend/src/services/correlation_service.py`
- `backend/src/services/correlation_snapshot_service.py`
- `backend/src/services/risk_factor_registry.py`
- `backend/src/services/risk_history_service.py`
- `backend/src/services/risk_scoring_service.py`
- `backend/tests/integration/test_correlation.py`

## 7. Sprint 10: Reporting & Analytics
- `backend/src/api/v1/routers/reports.py`
- `backend/src/domain/entities/report.py`
- `backend/src/services/asset_report_service.py`
- `backend/src/services/dashboard_service.py`
- `backend/src/services/dashboard_trend_service.py`
- `backend/src/services/executive_report_service.py`
- `backend/src/services/export_service.py`
- `backend/src/services/exposure_report_service.py`
- `backend/src/services/finding_report_service.py`
- `backend/src/services/report_cache_service.py`
- `backend/src/services/risk_report_service.py`
- `backend/tests/integration/test_reporting.py`

## 8. Sprints 38/39: Frontend Application Parity
- **Untracked Directory:** `frontend/` (87 files)
- **Includes:** Next.js scaffolding, generic components, pages for assets/findings/workflows/reports, Zustand state management, API services, and test suites.

## 9. Documentation
- `Implementation/RiskArchitecture.md`
- `Repository_State_Recovery_Report.md`
- `Working_Tree_Delta_Report.md`
