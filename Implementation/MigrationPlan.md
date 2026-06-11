# Database Migration Plan

This document defines the schema initialization and future migration strategy for AegisX, leveraging Alembic for PostgreSQL. It expands upon the Migration Strategy defined in `Docs/04_Database.md`.

## Tooling & Strategy

- **Migration Tool:** Alembic (Python).
- **ORM:** SQLAlchemy (declarative base).
- **Execution:** Migrations are run via `alembic upgrade head` during deployment or local setup. No manual schema modifications are permitted.
- **Versioning:** Migration scripts are checked into source control under `backend/alembic/versions/`.

## MVP Schema Phasing

To allow parallel development and stable testing, the initial v1.0 schema implementation will be broken down into specific Alembic revisions.

### Phase 1: Core Foundation & Assets (Revision: `rev_001_core`)
**Tables:** `users`, `scopes`, `assets`
- Implement UUID primary keys.
- Implement soft-deletion columns (`deleted_at`, `deleted_by`).
- Create indices on `assets` for fast lookup (`scope_id`, `host`, `ip`).
- Enable extensions: `uuid-ossp`, `pgcrypto`.

### Phase 2: Execution Engine (Revision: `rev_002_execution`)
**Tables:** `workflows`, `plugins`, `scan_runs`
- Foreign keys back to `users` and `scopes`.
- Add `state` text columns for workflows and plugins.
- Configure JSONB columns for `definition`, `manifest`, and `metrics`.

### Phase 3: Results & Artifacts (Revision: `rev_003_results`)
**Tables:** `findings`, `reports`, `artifacts`
- Foreign keys back to `assets`, `scan_runs`, `workflows`.
- Enforce unique constraint on finding `fingerprint`.
- Create JSONB indices on `findings(details)` and `findings(evidence)`.
- Configure text-search indexing if applicable.

### Phase 4: Observability & Intelligence (Revision: `rev_004_intel`)
**Tables:** `audit_logs`, `workflow_events`, `plugin_events`, `asset_relationships`, `asset_history`, `correlated_findings`, `risk_scores`
- Strict audit tables (insert-only tracking).
- Set up correlation indices (`correlation_group`).

## Safe Migration Policies (Post-MVP)

Once MVP data is in production, all future migrations must adhere to zero-downtime principles.

### 1. Expand-Then-Contract Pattern
Used when removing or renaming columns.
- **Step 1 (Expand):** Add the new column/table. Deploy the app to write to both the old and new schemas.
- **Step 2 (Migrate):** Backfill historical data in the background.
- **Step 3 (Contract):** Deploy the app to read/write only from the new schema. Drop the old column in a subsequent migration.

### 2. Concurrent Index Creation
When adding indices to large tables (e.g., `findings`, `assets`):
- Alembic must be configured to run outside a transaction block for concurrent indices.
- Use `CREATE INDEX CONCURRENTLY` to avoid table locks during deployment.

### 3. Avoiding Blocking Locks
- Never add a new column with a `DEFAULT` value on a large table (causes full table rewrite in older Postgres versions, though PG11+ handles constant defaults well). 
- If adding a `NOT NULL` column without a default, add it as nullable, backfill, then alter to `NOT NULL`.

---
Prepared by the Principal Software Architect for AegisX.
