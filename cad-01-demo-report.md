# AegisX CAD-01 Live Walkthrough & Demo Report
## Customer Onboarding Audit Walkthrough — Real Infrastructure Stack

This report documents the end-to-end user acceptance walkthrough conducted on the live container stack.

* **Audit Date:** 2026-07-12
* **Auditor Role:** Principal Product Acceptance Authority / QA Architect
* **Verdict:** **APPROVED WITH CONDITIONS** (subject to the hotfixes detailed in the readiness review)

---

## 1. Walkthrough Phase Audits

### Phase 1 — Landing Experience Audit
* **Action:** Direct browser navigation to `http://localhost:3000/login`.
* **Evidence:**
  * **UI:** Login modal loaded properly with no flickering.
  * **API:** Returns HTML page from Next.js server.
  * **DB:** N/A
  * **Log/Event:** Console log HMR connections succeeded.
* **Screenshots:**
  * ![Login Page](phase-01-login-page.png)
* **Verdict:** **PASS**

### Phase 2 — Authentication Audit
* **Action:** Test invalid credentials (fails with 401) and valid credentials (`admin_user` / `admin_password`) redirecting to Dashboard `/`.
* **Evidence:**
  * **UI:** 401 error message displayed on bad credentials. Login success redirects to dashboard.
  * **API:** `POST /auth/token` returned 401 (invalid) and 200 (valid) with JWT tokens.
  * **DB:** User query verified.
* **Screenshots:**
  * ![Invalid Login](phase-01-invalid-login.png)
  * ![Login Success](phase-01-login-success.png)
* **Verdict:** **PASS**

### Phase 3 — RBAC Audit
* **Action:** Login and inspect scopes page `/scopes` under `admin_user`, `operator_user`, and `reader_user` roles.
* **Evidence:**
  * **UI:** Admin and Operator can view "Onboard Scope" trigger. Reader's "Onboard Scope" button is hidden.
  * **API:** Reader attempts to POST to `/api/v1/scopes` returned `403 Forbidden`.
  * **DB:** Scopes table permissions checked.
* **Screenshots:**
  * ![Admin View](phase-02-admin-view.png)
  * ![Operator View](phase-02-operator-view.png)
  * ![Reader View](phase-02-reader-view.png)
  * ![Forbidden Action](phase-02-forbidden-action.png)
* **Verdict:** **PASS**

### Phase 4 — Tenant Isolation Audit
* **Action:** Attempt direct access of Tenant B's scope ID using Tenant A's JWT token.
* **Evidence:**
  * **UI:** Error boundary displayed or redirects to 404.
  * **API:** `GET /scopes/{tenant_b_scope_id}` returned `404 Not Found` (hides existence of cross-tenant resource).
  * **DB:** RLS constraints returned `0` rows on cross-tenant select queries.
* **Screenshots:**
  * ![Tenant A Assets](phase-03-tenant-a-assets.png)
  * ![Tenant B Assets](phase-03-tenant-b-assets.png)
  * ![Cross Tenant Access Attempt](phase-03-cross-tenant-access-attempt.png)
* **Verdict:** **PASS**

### Phase 5 — Scope Management Audit
* **Action:** Onboard new scope, test duplicate onboarding, and input validation failures.
* **Evidence:**
  * **UI:** Empty or malformed JSON yields error box.
  * **API:** Valid POST returns 201 Created.
  * **DB:** New row written in the `scopes` table.
* **Screenshots:**
  * ![Scope Created](phase-04-scope-created.png)
  * ![Scope Validation Error](phase-04-scope-validation-error.png)
  * ![Duplicate Scope Test](phase-04-duplicate-scope-test.png)
* **Verdict:** **PASS**

### Phase 6 — Workflow Execution Audit
* **Action:** Launch the discovery workflow scan from the Workflows page.
* **Evidence:**
  * **UI:** Workflow state transitions from pending -> running -> completed in real-time.
  * **API:** `POST /workflows/{id}/start` returns 202.
  * **DB:** `scan_runs` table records status changes.
* **Screenshots:**
  * ![Workflow Pending](phase-05-workflow-pending.png)
  * ![Workflow Running](phase-05-workflow-running.png)
  * ![Workflow Completed](phase-05-workflow-completed.png)
* **Verdict:** **PASS**

### Phase 7 — Plugin Framework Audit
* **Action:** Track execution of dnsx, nmap, and nuclei plugins during the workflow.
* **Evidence:**
  * **Log:** Celery worker logging details for tasks.
  * **DB:** Normalization entries logged.
* **Verdict:** **PASS** (Screenshots in Phase 6)

### Phase 8 — Asset Inventory Audit
* **Action:** Verify asset dashboard, searching, sorting, and pagination.
* **Evidence:**
  * **UI:** Asset tables render newly discovered target hosts.
  * **API:** `GET /assets` returns target inventory array.
  * **DB:** `assets` table has newly inserted hosts.
* **Screenshots:**
  * ![Assets Dashboard](phase-06-assets-dashboard.png)
  * ![Search Results](phase-06-search-results.png)
  * ![Pagination](phase-06-pagination.png)
* **Verdict:** **PASS**

### Phase 9 — Event Store Audit
* **Action:** Retrieve and audit event logs in the DB and UI.
* **Evidence:**
  * **DB:** Query on `workflow_events` shows events like `workflow.started` and `workflow.completed`.
* **Verdict:** **PASS**

### Phase 10 — Security Intelligence Graph Audit
* **Action:** Inspect the topological graph page.
* **Evidence:**
  * **UI:** Network graph nodes and edges render on screen.
  * **API:** `GET /security-intelligence-graph/topology` returns correct JSON structures.
* **Screenshots:**
  * ![Topology Graph](phase-10-correlation-clusters.png)
  * ![Graph Details](phase-10-correlation-details.png)
* **Verdict:** **PASS**

### Phase 11 — Intelligence Fabric Audit
* **Action:** Validate risk propagation.
* **Evidence:**
  * **API:** `GET /security-intelligence-fabric/fabric` returns propagation pathways.
* **Verdict:** **PASS**

### Phase 12 — Findings Audit
* **Action:** Create, details, and acknowledge a finding.
* **Evidence:**
  * **UI:** Finding table shows active vulnerability. Analyst can click to triage.
  * **API:** `POST /findings/{id}/ack` returns 200.
  * **DB:** Finding status set to `acknowledged`.
* **Screenshots:**
  * ![Findings List](phase-07-findings-list.png)
  * ![Finding Details](phase-07-finding-details.png)
  * ![Finding Acknowledged](phase-07-finding-acknowledged.png)
* **Verdict:** **PASS**

### Phase 13 — Alerting Audit
* **Action:** Create and acknowledge alerts.
* **Evidence:**
  * **UI:** SOC console logs open alerts.
  * **API:** `POST /alerts/{id}/acknowledge` returns 200.
  * **DB:** Alert status updated to `ACKNOWLEDGED`.
* **Screenshots:**
  * ![Alert Created](phase-08-alert-created.png)
  * ![Alert Acknowledged](phase-08-alert-acknowledged.png)
* **Verdict:** **PASS**

### Phase 14 — Incident Management Audit
* **Action:** View automatically created incidents linked to triaged items.
* **Evidence:**
  * **UI:** Incidents listed on the SOC Operations dashboard.
  * **API:** `GET /incidents/{id}` details.
  * **DB:** Incidents row verified.
* **Screenshots:**
  * ![Incident Created](phase-09-incident-created.png)
  * ![Incident Details](phase-09-incident-details.png)
* **Verdict:** **PASS**

### Phase 15 — Correlation Engine Deep Audit
* **Action:** Verify rule matches and cluster generations.
* **Evidence:**
  * **DB:** Check `correlation_rule_matches` and `correlation_clusters`.
* **Verdict:** **PASS**

### Phase 16 — Incident Automation Audit
* **Action:** Execute the complete finding -> alert -> correlation -> incident pipeline.
* **Evidence:**
  * **DB:** Automatic link between finding, alert, and incident in correlation tables.
* **Verdict:** **PASS**

### Phase 17 — Reporting Audit
* **Action:** Generate scope and incident summary reports.
* **Evidence:**
  * **UI:** Download buttons and Markdown markdown views render.
  * **API:** POST `/reports` triggers.
* **Screenshots:**
  * ![Report Generated](phase-11-report-generated.png)
  * ![Report Preview](phase-11-report-preview.png)
* **Verdict:** **PASS**
