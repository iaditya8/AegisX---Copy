# AegisX CAD-01 Defect Register Report
## Product Quality Audit Defect Registry

This register details all architectural, backend, database, UI, UX, and security defects identified during the live runtime quality audit.

---

### ID: CAD-01-DEF-001
* **Severity:** CRITICAL
* **Category:** Backend / API
* **Location:** `backend/src/domain/entities/asset.py` (`AssetResponse` model)
* **Description:** The `AssetResponse` API response schema is annotated with `ip: Optional[str]`. However, SQLAlchemy maps the PostgreSQL `INET` column to a Python `ipaddress.IPv4Address` object. When serialization runs on asset retrieval endpoints, Pydantic v2 fails to serialize the object, yielding a `TypeValidationError` (500 Internal Server Error).
* **Reproduction Steps:**
  1. Populate an asset with an IP in the database.
  2. Invoke `GET /api/v1/assets/{id}` or `GET /api/v1/scopes/{id}/assets`.
* **Expected Result:** API returns the serialized asset JSON with the IP address formatted as a string.
* **Actual Result:** API returns `500 Internal Server Error` due to Pydantic type validation failure.
* **Impact:** Absolute blocker for all asset inventory UI page views.
* **Root Cause:** Missing type coercion validator in Pydantic schema for database `INET` / `IPv4Address` fields.
* **Recommendation:** Add a `@field_validator('ip', mode='before')` to `AssetResponse` to string-coerce the incoming value.

---

### ID: CAD-01-DEF-002
* **Severity:** CRITICAL
* **Category:** Database
* **Location:** PostgreSQL Database (`correlation_clusters` table)
* **Description:** The `CorrelationCluster` SQLAlchemy model inherits from `AuditMixin`, requiring columns `created_by` and `updated_by`. However, these columns were missing from the physical table in the PostgreSQL database, causing all correlation query routes to fail with `UndefinedColumnError`.
* **Reproduction Steps:**
  1. Trigger a correlation cluster query via `GET /api/v1/correlations/clusters`.
* **Expected Result:** Database executes the query successfully.
* **Actual Result:** SQL query throws `ProgrammingError: column "created_by" does not exist`.
* **Impact:** Renders the unified correlation engine and clusters interface completely unusable.
* **Root Cause:** The database migration `a9b8c7d6e5f4_create_correlation_tables.py` omitted the `created_by` and `updated_by` columns.
* **Recommendation:** Apply DDL changes to add the columns to the database.

---

### ID: CAD-01-DEF-003
* **Severity:** CRITICAL
* **Category:** Backend
* **Location:** `backend/src/services/asset_exposure_service.py` (`is_public_ip` method)
* **Description:** The `is_public_ip` method calls `.strip()` on the input IP address argument. When the risk calculator passes a mapped `IPv4Address` object from the database, the method crashes with `AttributeError: 'IPv4Address' object has no attribute 'strip'`.
* **Reproduction Steps:**
  1. Trigger asset risk score updates during scanning.
* **Expected Result:** Risk score propagates with no errors.
* **Actual Result:** Celery worker task fails with an `AttributeError`.
* **Impact:** Prevents scan result normalization, risk scoring, and intelligence fabric propagation.
* **Root Cause:** Missing type checks and string coercion on the input parameter before calling string functions.
* **Recommendation:** Coerce the input value to string (`str(ip_str).strip()`) before parsing.

---

### ID: CAD-01-DEF-004
* **Severity:** CRITICAL
* **Category:** Database / API
* **Location:** `backend/src/services/finding_service.py`
* **Description:** Triaging a finding generates a `WorkflowEvent` using a random `uuid.uuid4()` as the `workflow_id`. Because the database enforces a foreign key constraint linking `workflow_events(workflow_id) REFERENCES workflows(id)`, this operation fails with `ForeignKeyViolationError` and rolls back the transaction.
* **Reproduction Steps:**
  1. Login and navigate to a finding.
  2. Click Acknowledge or Resolve.
* **Expected Result:** Finding status changes and audit log event is written.
* **Actual Result:** API returns `500 Internal Server Error` due to constraint violation.
* **Impact:** Blockers for findings triage and audit tracking.
* **Root Cause:** Random UUID generation instead of resolving a valid database workflow ID.
* **Recommendation:** Query for the first active workflow in the DB or bootstrap a placeholder workflow to satisfy constraints.

---

### ID: CAD-01-DEF-005
* **Severity:** HIGH
* **Category:** Security / RBAC
* **Location:** `backend/src/api/v1/routers/scopes.py`
* **Description:** The Operator role is not read-only for scopes in the UI or API. An operator user can successfully create, update, and delete target scopes without administrative permissions.
* **Reproduction Steps:**
  1. Log in as `operator_user`.
  2. Onboard a new scope.
* **Expected Result:** Action is rejected or disabled based on RBAC rules.
* **Actual Result:** Scope is successfully created (201 Created).
* **Impact:** Security boundary violation allowing operators to define scope ranges without admin approval.
* **Root Cause:** Incomplete permission check rules in scopes router endpoints.
* **Recommendation:** Apply strict `RoleChecker` restrictions to scope write endpoints.

---

### ID: CAD-01-DEF-006
* **Severity:** MEDIUM
* **Category:** UI / UX
* **Location:** `frontend/src/app/login/page.tsx`
* **Description:** Entering invalid credentials returns a raw request error but fails to update the visual UI notification form error box in all cases, leaving the user with no visual feedback.
* **Reproduction Steps:**
  1. Go to `/login` and submit incorrect username/password.
* **Expected Result:** Visual red error box indicating bad credentials.
* **Actual Result:** Browser console records 401 but UI does not show explicit warning message in some conditions.
* **Impact:** Poor first-time login experience and confusing error presentation.
* **Recommendation:** Update error handling inside the React `handleSubmit` function to catch 401 statuses explicitly and update the state.
