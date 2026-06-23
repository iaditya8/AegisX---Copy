# Working Tree Delta Report

## File Counts
1. **Total modified files:** 18
2. **Total untracked files:** 149

## Inventory Analysis

### 3. Frontend file inventory
**Status:** Entirely Untracked
The `frontend/` directory is completely uncommitted. It contains 87 untracked files forming a complete Next.js React application, including:
- **Pages/Routing:** 15 files (App router structure for assets, findings, workflows, scopes, reports, login)
- **Components:** 17 files (e.g., `AssetTable.tsx`, `FindingTable.tsx`, `ReportDashboard.tsx`, `ScanRunMonitor.tsx`)
- **State & Hooks:** 2 stores (`auth.ts`, `scope.ts`), 5 custom hooks
- **API Services:** 6 service modules mapping to the backend
- **Config & Setup:** 12 framework config files (Next, Tailwind, ESLint, Playwright, Vitest)

### 4. Backend file inventory
**Status:** 17 Modified, 59 Untracked
The backend working tree contains massive uncommitted additions representing several sprints of work.

### 5. New routers added beyond Sprint 4
**Untracked (4):**
- `correlations.py`
- `findings.py`
- `plugins.py`
- `reports.py`
*(Note: `scan_runs.py` and `workflows.py` are modified)*

### 6. New services added beyond Sprint 4
**Untracked (33):**
The working tree introduces 33 new service modules that are completely untracked. Notable additions include:
- **Asset Intelligence:** `asset_intelligence_service.py`, `asset_exposure_service.py`, `asset_criticality_service.py`
- **Findings & Normalization:** `finding_service.py`, `finding_normalization_service.py`, `finding_reconciliation_service.py`
- **Correlation & Risk:** `correlation_service.py`, `risk_scoring_service.py`, `risk_history_service.py`
- **Reporting:** `executive_report_service.py`, `dashboard_service.py`, `export_service.py`
- **Plugins Orchestration:** `plugin_service.py`, `discovery_normalization_service.py`, `service_normalization_service.py`

### 7. New tests added beyond Sprint 4
**Untracked Backend Tests (6):**
- `test_correlation.py`, `test_findings.py`, `test_plugins.py`, `test_recon_plugins.py`, `test_reporting.py`, `test_service_discovery.py`
**Untracked Frontend Tests (8):**
- Playwright E2E (`sprint39.spec.ts`), Vitest Units (`sprint38.test.tsx`, `sprint39.test.tsx`), and MSW mock infrastructure.

### 8. New database models added beyond Sprint 4
`models.py` is in a **Modified** state. It contains definitions for numerous advanced entities that do not align with a Sprint 4 baseline:
- `Plugin`, `Finding`, `FindingEvidence`, `FindingHistory`
- `Report`, `Artifact`
- `AssetRelationship`, `CorrelatedFinding`, `RiskScore`, `AssetPort`, `AssetService`

### 9. New Celery tasks added beyond Sprint 4
`worker.py` is in a **Modified** state. It contains highly complex logic for plugin orchestration (`PluginHost`), finding normalization, and snapshot generation that vastly exceeds the Sprint 4 "Celery integration" commit message.

### 10. Estimated implementation progress based on current files
Based on the uncommitted working tree, the repository has actually been implemented up through **Phase 2 (Asset Intelligence & Correlation)** and **Sprint 11 (Frontend Parity)**. The code handles sophisticated vulnerability processing, nuclei template tracking, plugin sandboxing, risk scoring, and contains a fully functional React frontend interface.

---

## State Comparison

### A. HEAD commit state
**Commit:** `2c0fdb9 Sprint 4 complete: workflows, scan runs, Celery integration, and database migration alignment`
The Git history implies the project is in its infancy. If the working tree were wiped (e.g., `git reset --hard`), the repository would revert to a skeletal backend capable only of basic auth, scope CRUD, and rudimentary celery task queuing. 

### B. Current working tree state
The actual workspace represents the culmination of **Sprint 11 / Sprint 39**. A massive volume of code (149 untracked files, 18 heavily modified files) has been written, tested, and integrated without ever being committed to source control. The perceived "inconsistencies" from earlier audits were the result of evaluating the project's state solely by its Git history rather than analyzing the uncommitted physical files sitting in the directory.
