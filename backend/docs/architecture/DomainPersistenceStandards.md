# AegisX Domain Persistence Standards

This document establishes the official standards for all domain persistence migrations within AegisX. All future database integrations must conform strictly to these patterns.

## 1. Core Schema Standards

### Mandatory Tenant Isolation
Every table containing customer data must include a `tenant_id` column.
- Data type: `UUID`
- Foreign Key: `REFERENCES tenants(id) ON DELETE CASCADE`
- Nullability: `NOT NULL`

### Mandatory Timestamps & Audit Fields
All transactional tables must track the lifecycle of each record and the user who modified it:
- `created_at`: Timestamp (with time zone), defaulted to `now()`, nullable=False.
- `updated_at`: Timestamp (with time zone), defaulted to `now()`, updated on modification, nullable=False.
- `created_by`: UUID, foreign key referencing `users.id` (set null on delete), nullable=True.
- `updated_by`: UUID, foreign key referencing `users.id` (set null on delete), nullable=True.

### Soft Delete Strategy
To prevent accidental data loss and maintain compliance trails, database deletion must use soft deletes instead of hard deletes:
- `is_deleted`: Boolean, default `False`, nullable=False.
- `deleted_at`: Timestamp (with time zone), nullable=True.
- `deleted_by`: UUID, foreign key referencing `users.id`, nullable=True.
- Repositories must filter out `is_deleted = True` records by default, unless explicitly requested.

### Optimistic Locking
To prevent lost updates under high concurrency, versioning is mandatory:
- `version`: Integer, default `1`, incremented automatically on every update.
- Handled at the SQLAlchemy mapper level using `version_id_col`.

---

## 2. Shared Database Mixins

All new database models must inherit from standard mixins defined in `backend/src/infrastructure/database/mixins.py`:
- `TenantOwnedMixin`
- `AuditMixin`
- `VersionedMixin`
- `SoftDeleteMixin`

---

## 3. Row Level Security (RLS) Requirements

1. **Policy Enforcement**: Row Level Security must be explicitly enabled on all tables:
   ```sql
   ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;
   ALTER TABLE <table_name> FORCE ROW LEVEL SECURITY;
   ```
2. **Tenant Isolation Policy**: The default policy must check the session parameter `app.current_tenant`:
   ```sql
   CREATE POLICY tenant_isolation ON <table_name>
   USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
   ```

---

## 4. Architectural Patterns

### Write Path
1. **Database-First**: All writes (inserts, updates, deletes) must commit to PostgreSQL first within a `UnitOfWork` session block.
2. **Outbox Event**: If the entity has CQRS read projections or integrations, a corresponding outbox event must be written inside the *same database transaction*.
3. **L2 Invalidation**: Cache entries must only be invalidated or updated *after* the database commit succeeds.

### Read Path
1. **L2 Cache Lookup**: Check `CacheDict` (backed by Redis/Memory). If a hit occurs, return immediately.
2. **Database Fallback**: If a cache miss occurs, query via the repository layer.
3. **Rehydrate Cache**: Save the query result back into `CacheDict` before returning.

### Caching and Invalidation
- **Cache invalidation**: Any write, update, or soft-deletion must invalidate the entity cache, list query cache, and any aggregated dashboard query cache immediately.

---

## 5. Repository & UnitOfWork Usage
- Domain services must *never* perform direct SQLAlchemy queries or call `session.commit()` / `session.execute()`.
- All operations must be routed through specific domain repositories (e.g. `CyberRiskRepository`) retrieved via an active `UnitOfWork` instance.
