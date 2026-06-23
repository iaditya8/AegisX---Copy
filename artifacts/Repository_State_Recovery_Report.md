# Repository State Recovery Report

## 1. Actual roadmap position
Based on the physical files, the repository contains the foundation for **Phase 1 (MVP)** and the initial components of **Phase 2 (Asset Intelligence)**. The application currently supports Scope Management, Asset Discovery, Vulnerability Integration (Findings), Scan Orchestration (Workflows/Plugins), and basic Correlation. It has not yet implemented the AI Security Copilot (Phase 3) or Enterprise Features (Phase 4).

## 2. Actual completed sprint number
**Sprint 4**. The git commit history consists of exactly one commit: `2c0fdb9 Sprint 4 complete: workflows, scan runs, Celery integration, and database migration alignment`.

## 3. Router inventory
There are **11 API routers** physically present in `backend/src/api/v1/routers/`:
1. `assets.py`
2. `auth.py`
3. `correlations.py`
4. `findings.py`
5. `health.py`
6. `plugins.py`
7. `reports.py`
8. `scan_runs.py`
9. `scopes.py`
10. `users.py`
11. `workflows.py`

## 4. Endpoint inventory
These 11 routers implement standard REST CRUD patterns, equating to an estimated **35-45 functional endpoints**.

## 5. Service inventory
There are **39 service modules** physically present in `backend/src/services/`, representing the core business logic. Notable services include:
- `asset_service.py`, `asset_intelligence_service.py`, `asset_risk_snapshot_service.py`
- `finding_service.py`, `finding_normalization_service.py`, `finding_reconciliation_service.py`
- `workflow_service.py`, `plugin_service.py`, `correlation_service.py`, `risk_scoring_service.py`
- `executive_report_service.py`, `dashboard_service.py`, `audit_service.py`

## 6. Database model inventory
There are **20 SQLAlchemy models** physically defined in `backend/src/infrastructure/database/models.py`:
- `User`, `Scope`, `Asset`, `Workflow`, `Plugin`, `ScanRun`
- `Finding`, `FindingEvidence`, `FindingHistory`
- `Report`, `Artifact`, `AuditLog`
- `WorkflowEvent`, `PluginEvent`
- `AssetRelationship`, `AssetHistory`, `CorrelatedFinding`, `RiskScore`
- `AssetPort`, `AssetService`

## 7. Celery workflow inventory
There is **1 registered Celery task** physically defined in `backend/src/infrastructure/celery/worker.py`:
- `@celery_app.task(name="execute_workflow_task")`

## 8. Existing frontend inventory
The frontend is a Next.js application containing the following structural layout:
- **Pages**: `login`, `scopes`, `assets`, `findings`, `workflows`, `reports`, `403`.
- **Components**: Grouped by domains corresponding to the pages, plus a `shared` folder for UI elements (e.g., `AssetTable.tsx`, `AssetTabs.tsx`, `FindingTable.tsx`).
- **State Management**: Zustand stores for auth (`auth.ts`) and scopes (`scope.ts`).

## 9. Existing test inventory
- **Backend Tests**: 12 integration test files in `backend/tests/integration/` targeting assets, auth, correlation, findings, health, plugins, recon_plugins, reporting, scopes, service_discovery, users, and workflows.
- **Frontend Tests**: E2E test file (`sprint39.spec.ts`) utilizing Playwright, and unit test files (`sprint38.test.tsx`, `sprint39.test.tsx`) utilizing Vitest/MSW.

## 10. Missing roadmap documents
The following requested documents are **not present** anywhere on the physical disk:
- `frontend_readiness_and_roadmap_corrections.md`
- `frontend_implementation_blueprint.md`
- `post_audit_verification_report.md`
- `implementation_plan_sprint38.md`

## 11. Gap analysis between repository state and planned state
- **Sprint Desync:** The frontend test files assert progression up to "Sprint 39," while the backend implementation plan (`implementation_plan.md`) anticipates "Sprint 12." However, the definitive repository ground truth (Git history) demonstrates that the project is strictly at **Sprint 4**.
- **Missing Correction Data:** The planning and roadmap correction artifacts requested for review do not physically exist. Any strategic pivots that relied on those documents lack representation in the repository.
- **Implementation Reality:** The codebase represents a solid Phase 1 (MVP) structure with early Phase 2 elements. Assertions that the project had reached Sprint 38 or entered advanced Copilot/SaaS stages are completely disconnected from the actual code on disk.
