# API Specification (REST)

This document defines the REST endpoints, authentication model, request/response shapes, error handling, and pagination strategy for AegisX. The implementation target is FastAPI (OpenAPI compatible) as described in `Docs/03_Architecture.md`.

## Principles

- OpenAPI-first: every endpoint must be documented and validated.  
- Use JWT Bearer tokens for authentication (MVP) with RBAC checks for authorization.  
- Keep endpoints idempotent where appropriate and support idempotency keys for create operations.  
- Responses must be consistent: wrap metadata separately from data and include trace ids for debugging.

## API Versioning

All endpoints must be prefixed with `/api/v1/`.

Strategy and Backward Compatibility:
- **Major Versioning**: The `v1` prefix indicates the major version. Breaking changes (e.g., removing fields, changing data types, or fundamentally altering endpoint behavior) require a new major version (e.g., `/api/v2/`).
- **Additive Changes**: We will add fields, endpoints, or optional query parameters to the existing `v1` API without changing the major version. Clients must be resilient to new fields in responses.
- **Deprecation**: Deprecated endpoints will include a `Deprecation` header and will be supported for at least 6 months before removal.

## Authentication

- Scheme: `Authorization: Bearer <JWT>`.
- Token contents: `sub` (user id), `roles` (array), `exp` (expiry), `iss`.
- Refresh: issue refresh tokens via `POST /api/v1/auth/refresh` (refresh token stored securely by client).  
- RBAC: server enforces role checks (admin, operator, reader).  
- Optional: API keys for automation (short-lived) issued per-user and stored hashed in DB.

## Common headers

- `Authorization: Bearer <token>` — authentication.  
- `Idempotency-Key: <uuid>` — optional for POST operations to ensure idempotent creates.  
- `X-Trace-Id: <uuid>` — optional client-provided trace id; server returns the same in responses.

## Standard Success Response

All successful API responses (unless returning a raw file download) must adhere to the following standard structure:

```json
{
  "success": true,
  "data": {},
  "meta": {},
  "trace_id": "..."
}
```

- `success`: Boolean indicating operation success.
- `data`: The primary resource or list of resources. Can be an object or an array.
- `meta`: Pagination details, counts, or other secondary metadata.
- `trace_id`: The server trace ID for debugging and correlation.

## Error response model

All errors return JSON with HTTP status codes and this shape:

```json
{
  "error": {
    "code": "string",        // machine code, e.g. invalid_input, unauthorized
    "message": "string",     // human-friendly message
    "details": { },            // optional object with field errors
    "trace_id": "uuid"       // server trace id for debugging
  }
}
```

Status codes and usage:
- `200 OK` — successful GET/PUT/DELETE responses.  
- `201 Created` — resource created. Include `Location` header.  
- `202 Accepted` — asynchronous job accepted (e.g., workflow started).  
- `400 Bad Request` — validation errors.  
- `401 Unauthorized` — missing/invalid token.  
- `403 Forbidden` — insufficient privileges.  
- `404 Not Found` — resource missing.  
- `409 Conflict` — idempotency or uniqueness conflict.  
- `429 Too Many Requests` — rate limited.  
- `500/503` — server errors; include `trace_id`.

## REST Endpoints (summary)

Auth
- `POST /api/v1/auth/token` — exchange credentials for JWT. Request: {username, password}. Response: {access_token, expires_in, refresh_token?}.  
- `POST /api/v1/auth/refresh` — exchange refresh token for new access token.

Users
- `GET /api/v1/users` — list users (admins only). Supports pagination.  
- `POST /api/v1/users` — create user (admin).  
- `GET /api/v1/users/{user_id}` — user details.  
- `PUT /api/v1/users/{user_id}` — update user.  
- `DELETE /api/v1/users/{user_id}` — remove user (soft-delete recommended).

Scopes & Assets
- `GET /api/v1/scopes` — list scopes (filter by owner).  
- `POST /api/v1/scopes` — create scope (body: name, type, definition).  
- `GET /api/v1/scopes/{id}` — scope detail.  
- `PUT /api/v1/scopes/{id}` — update scope.  
- `DELETE /api/v1/scopes/{id}` — delete scope.
- `GET /api/v1/scopes/{id}/assets` — list assets in scope (paginated, filter by host/ip).  
- `GET /api/v1/assets/{id}` — asset detail.

Asset Intelligence
- `GET /api/v1/assets/{id}/relationships` — Retrieve relationships to other assets or infrastructure components.
- `GET /api/v1/assets/{id}/history` — Retrieve historical changes and timeline for the asset.
- `GET /api/v1/assets/{id}/risk` — Retrieve computed risk context and exposure scores for the asset.

Workflows & Scan Runs
- `POST /api/v1/workflows` — create workflow definition (body includes steps). Returns `201` with workflow id.  
- `POST /api/v1/workflows/{id}/start` — start execution; returns `202 Accepted` with `run_id`.  
- `GET /api/v1/workflows/{id}` — workflow status and recent runs.  
- `GET /api/v1/workflows/{id}/events` — Expose workflow lifecycle events, transitions, and debugging information. Supports pagination and filtering (e.g., by event type or timestamp).
- `GET /api/v1/scan_runs/{id}` — scan run status, metrics, links to artifacts.  
- `POST /api/v1/scan_runs/{id}/cancel` — request cancellation.

Findings & Correlation
- `GET /api/v1/findings` — list findings with filters (severity, scanner, scope_id, asset_id). Supports pagination and sort.  
- `GET /api/v1/findings/{id}` — find details.  
- `POST /api/v1/findings/{id}/ack` — acknowledge or triage a finding (human-in-loop action).
- `GET /api/v1/correlations` — Expose correlated findings and risk analysis. Supports filtering by risk score, severity, or asset.
- `GET /api/v1/correlations/{id}` — Retrieve details of a specific correlation event or finding group.

Reports & Artifacts
- `GET /api/v1/reports` — list generated reports.  
- `GET /api/v1/reports/{id}` — metadata; `GET /api/v1/reports/{id}/download` — presigned link or redirect to object store.  
- `GET /api/v1/artifacts/{id}` — fetch artifact metadata or download.

Plugins & Admin
- `GET /api/v1/plugins` — list installed plugins (admin).  
- `POST /api/v1/plugins` — register/install plugin (admin).  
- `POST /api/v1/plugins/{id}/validate` — run plugin self-check.
- `POST /api/v1/plugins/{id}/approve` — Mark a plugin as approved for execution. Admins only. State transitions must respect lifecycle rules.
- `POST /api/v1/plugins/{id}/disable` — Prevent a plugin from executing. Admins only.
- `POST /api/v1/plugins/{id}/deprecate` — Prevent new installations of a plugin. Admins only.

Audit Logs
- `GET /api/v1/audit-logs` — List system and user audit events. Admins only. Supports filtering by user, action, and timestamp, along with pagination.
- `GET /api/v1/audit-logs/{id}` — Retrieve detailed information for a specific audit log entry. Admins only.

Health & Observability
- `GET /api/v1/healthz` — simple health check.  
- `GET /api/v1/readyz` — readiness.  
- `GET /api/v1/metrics` — Prometheus metrics (or exported separately).

## Request Models (examples)

Create Scope (POST /api/v1/scopes)

```json
{
  "name": "acme-internet",
  "type": "domain",
  "definition": {
    "domains": ["acme.com", "acme-ops.com"],
    "exclude": ["dev.acme.com"]
  }
}
```

Create Workflow (POST /api/v1/workflows)

```json
{
  "name": "daily-discovery",
  "owner_id": "uuid",
  "definition": {
    "steps": [
      {"type":"discovery", "config": {"tools":["subfinder","amass"]}},
      {"type":"port-scan", "config": {"tools":["naabu"]}},
      {"type":"http-check", "config": {"tools":["httpx"]}},
      {"type":"nuclei", "config": {"templates":["default"]}}
    ]
  }
}
```

Start Workflow (POST /api/v1/workflows/{id}/start)

```json
{ "scope_id": "uuid", "triggered_by": "user-id", "options": { "fast_mode": true } }
```

## Response Models (examples)

List Findings (200)

```json
{
  "success": true,
  "data": [ { "id":"...", "asset_id":"...", "severity":"high", "title":"..." } ],
  "meta": { "total": 1234, "limit": 50, "cursor": "abc123" },
  "trace_id": "..."
}
```

Start Workflow (202)

```json
{
  "success": true,
  "data": {
    "workflow_id": "uuid",
    "run_id": "uuid",
    "status": "accepted"
  },
  "meta": {},
  "trace_id": "..."
}
```

Error (example 400)

```json
{
  "error": { "code":"invalid_input", "message":"validation failed","details": {"name":"required"}, "trace_id":"..." }
}
```

## Pagination

Strategy: support cursor-based pagination for large/streaming datasets and offset-based for simple admin views. Provide `limit` and either `cursor` (opaque token) or `page`/`per_page`.

Parameters:
- `limit` (int, default 50, max 1000).  
- `cursor` (opaque string) — returned from responses when using cursor pagination.  
- `page`/`per_page` — optional legacy offset pagination.

Response metadata:
- `meta.total` — coarse total (may be estimated for large sets).  
- `meta.cursor` — next cursor to fetch.  
- `links` — optional link headers: `first`, `prev`, `next`, `last`.

Example cursor request:

`GET /api/v1/findings?limit=100&cursor=eyJvZmZzZXQiOjEwMH0=`

Example response meta:

```json
{
  "success": true,
  "meta": { "limit": 100, "cursor": "eyJvZmZzZXQiOjEwMH0=", "total": 12345 },
  "data": [ ... ],
  "trace_id": "..."
}
```

Guidelines:
- Use cursor pagination for endpoints that stream changes (assets, findings, scan_runs).  
- For UI pagination with stable totals (admin lists), offset pagination is acceptable.

## Idempotency and retries

- Require `Idempotency-Key` for operations that create external side effects (start workflow, create scan_run).  
- Server stores idempotency results for a configurable TTL and returns `409 Conflict` for duplicate conflicting requests.

## Rate Limiting

- Surface `429 Too Many Requests` with `Retry-After` header.  
- Apply per-user and per-API-key limits.  

## Observability & Tracing

- All responses include `trace_id` for correlation.  
- Events emitted to the bus include `trace_id` to connect API requests to worker actions.

## OpenAPI & Validation

- Generate OpenAPI spec from endpoint definitions (FastAPI/Pydantic).  
- Validate incoming payloads strictly and return `400` on schema mismatch.  

## Notes and Next Steps

- Create an OpenAPI YAML/JSON export and add it to the repo (`openapi.json`).  
- Optionally generate typed client SDKs (TypeScript/Python) from the OpenAPI spec.

---
Prepared by the API Architect for AegisX.
