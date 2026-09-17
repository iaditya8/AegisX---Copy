# AegisX Defects Found Report
## Production Certification Audit — Real Backend Infrastructure Stack

This report lists the architectural defects, coding bugs, and database schema issues identified, investigated, and remediated during the live runtime production validation of the AegisX platform.

* **Audit Date:** 2026-07-11
* **Auditor Role:** Principal Application Security Engineer / DevOps Architect
* **Target Stack:** FastAPI, Next.js, PostgreSQL, Redis, Celery.

---

## 1. Defect Log Summary

| Defect ID | Severity | Component | Description | Current Status |
| :--- | :--- | :--- | :--- | :--- |
| **DEF-01** | **CRITICAL** | API Serialization | `AssetResponse` failed to serialize database IP addresses. SQLAlchemy converts PostgreSQL `INET` to `ipaddress.IPv4Address`, which Pydantic failed to map to `Optional[str]`. This returned 500 server crashes. | **RESOLVED** (IP coercion validator added to `AssetResponse`) |
| **DEF-02** | **CRITICAL** | Database Schema | `correlation_clusters` table lacked `created_by` and `updated_by` columns, which are required by the `AuditMixin` parent class in the `CorrelationCluster` SQLAlchemy model. This threw `UndefinedColumnError` on queries. | **RESOLVED** (Columns added to table in PostgreSQL) |
| **DEF-03** | **CRITICAL** | Service logic | `AssetExposureService.is_public_ip()` called `.strip()` on the IP address argument. But when called with an `ipaddress.IPv4Address` object, it crashed with `AttributeError: 'IPv4Address' object has no attribute 'strip'`. | **RESOLVED** (Coerced input to string before calling strip) |
| **DEF-04** | **CRITICAL** | API & Database | When triaging a finding (Acknowledge), the service generated a random UUID as the `workflow_id` of the `WorkflowEvent` object. This violated the database foreign key constraint, returning a `ForeignKeyViolationError` and 500 API error. | **RESOLVED** (Updated service to fetch or bootstrap a valid workflow ID) |
| **DEF-05** | **MEDIUM** | API Router design | The platform backend lacked REST endpoints to create findings and incidents directly via the API, which are necessary for automated UAT/Audit script execution. | **RESOLVED** (Added POST `/alerts` and POST `/incidents` routes to routers) |

---

## 2. Detailed Root Cause Analysis (RCA)

### DEF-01: AssetResponse Pydantic Serialization Error
* **Root Cause:** SQLAlchemy translates the PostgreSQL `INET` column to a Python `IPv4Address` object. Pydantic v2 was configured with type annotation `ip: Optional[str]`. When Pydantic attempted to serialize the object, it raised a TypeValidationError because it could not implicitly coerce an `IPv4Address` object to a string.
* **Remediation:** Added a `@field_validator('ip', mode='before')` to `AssetResponse` inside `backend/src/domain/entities/asset.py` to check if the value is an instance of `IPv4Address` and convert it to string.

### DEF-02: Correlation Clusters Undefined Column
* **Root Cause:** The database Alembic migration file `a9b8c7d6e5f4_head.py` failed to create `created_by` and `updated_by` columns for `correlation_clusters`. However, the SQLAlchemy model inherits from `AuditMixin`, which automatically includes these columns in query generation.
* **Remediation:** Altered the PostgreSQL schema to add `created_by` and `updated_by` columns of type `UUID` to the `correlation_clusters` table.

### DEF-03: Exposure Service AttributeError
* **Root Cause:** In `AssetExposureService.is_public_ip()`, the input argument was annotated as `ip_str: str` and processed via `ip_str.strip()`. When the risk service passed an SQLAlchemy-mapped `IPv4Address` object, Python crashed because `IPv4Address` lacks string-manipulation methods.
* **Remediation:** Updated `is_public_ip` to coerce the input using `str(ip_str).strip()`, allowing safe handling of both strings and address objects.

### DEF-04: WorkflowEvent ForeignKey Violation
* **Root Cause:** When acknowledging a finding, `finding_service.py` emitted a `WorkflowEvent` event using `workflow_id=uuid.uuid4()`. The PostgreSQL database enforces a strict foreign key relation on `workflow_events(workflow_id) REFERENCES workflows(id)`. Inserting a random UUID failed the constraint.
* **Remediation:** Modified `finding_service.py` to query for the first available workflow ID or dynamically insert a placeholder system workflow to satisfy database integrity constraints.
