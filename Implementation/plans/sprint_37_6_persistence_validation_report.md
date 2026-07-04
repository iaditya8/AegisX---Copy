# AegisX RC-1 Validation Review — CRIT-06 Persistence Verification

**Auditors:** Principal Software Architect, Principal Database Architect, Principal Backend Architect
**Date:** 2026-07-04
**Objective:** Validate the accuracy of RC-1 Finding CRIT-06 ("In-Memory State for All Service Caches - Data Loss on Restart").

---

## Deliverable 1: Persistence Status Matrix

| Domain | Persisted? | Storage Type | Restart Safe? |
| :--- | :--- | :--- | :--- |
| **Cyber Resilience** | Not Persisted | Memory Only | No |
| **SOC Analytics** | Not Persisted | Memory Only | No |
| **Risk Quantification** | Not Persisted | Memory Only | No |
| **GRC Intelligence** | Not Persisted | Memory Only | No |
| **Security Knowledge** | Not Persisted | Memory Only | No |
| **Threat Intelligence** | Not Persisted | Memory Only | No |
| **Security Intelligence Graph** | Not Persisted | Memory Only | No |
| **Security Decision Intelligence** | Not Persisted | Memory Only | No |
| **Autonomous Planning** | Not Persisted | Memory Only | No |
| **Unified Security Intelligence Fabric** | Not Persisted | Memory Only | No |

---

## Deliverable 2: CRIT-06 Accuracy Verdict

**Verdict:** **Accurate**

The claim made in the RC-1 Audit Report that *"Every restart of the API container loses all data..."* is factually correct.

**Evidence:**
1. **CacheDict Usage:** All listed domains utilize a custom `CacheDict` class (defined in `backend/src/infrastructure/cache/cache_dict.py`) to store their primary entities. For example, `GovernanceRiskComplianceService` uses `_assessments = CacheDict("grc_compliance")`.
2. **Storage Factory Fallback:** The `CacheDict` class resolves its backend via `StorageFactory.get_adapter()`. The factory looks for `settings.CACHE_PROVIDER`. Because this variable is completely absent from `backend/src/core/config.py`, `.env`, and `docker-compose.yml`, the factory permanently defaults to `"memory"`.
3. **MemoryStorageAdapter:** The memory adapter (`backend/src/infrastructure/cache/memory_storage_adapter.py`) uses a class-level dictionary (`_global_data: Dict[str, Dict[str, str]] = {}`) to store state. This resides entirely in the Python process memory. When the FastAPI container restarts, the Python process terminates, and all data within `_global_data` is irrevocably lost.
4. **Missing Database Models:** A thorough review of `backend/src/infrastructure/database/models.py` reveals that while core entities (Users, Scopes, Assets, Findings, Workflows, Reports) are mapped to PostgreSQL, **none** of the entities from Sprints 24–37.5 exist as SQLAlchemy models.
5. **Missing Alembic Migrations:** The `backend/alembic/versions` directory contains exactly two migrations (`rev_001_core_and_auth.py` and `rev_002_findings_sprint8.py`). There are zero migrations defining schema for GRC, Cyber Resilience, SOC Analytics, Threat Intel, etc.

---

## Deliverable 3: Persistence Gap Estimates

Because an estimated 80% of the platform's advanced business logic operates entirely in-memory, addressing this is a significant undertaking.

*   **Severity:** **Critical** (Total data loss on container restart; inability to scale horizontally across multiple API workers).
*   **Required Effort:** **High** (Estimated 3–4 weeks for a dedicated backend engineering team).
*   **Number of Tables Likely Needed:** **~25–35 tables** (Each domain requires 2-4 tables for its core entities, history tracking, mapping tables, and objective configurations).
*   **Number of Migrations Likely Needed:** **~10 migrations** (Ideally chunked by domain, e.g., `rev_003_grc.py`, `rev_004_soc_analytics.py`, etc., or one massive schema migration).

---

## Deliverable 4: Final Verdict

**B) Persistence Architecture Program is required before RC-2**

**Code-Level Justification:**
AegisX cannot proceed to RC-2 in its current state. The application currently functions as a highly complex, stateful monolith that stores its most valuable security data in transient dictionaries. 
*   If a customer uploads GRC evidence, it is placed in a dictionary.
*   If an executive generates a cyber resilience scorecard, it is placed in a dictionary.
*   If a container orchestrator (e.g., Kubernetes) restarts the API pod for a routine update, or if the server reboots, **100% of the customer's advanced security configuration and history is deleted**.
*   Furthermore, because `MemoryStorageAdapter` is process-bound, AegisX cannot run multiple load-balanced API instances, as each instance would maintain a divergent, isolated state.

A comprehensive Persistence Architecture Program must be executed to map these domain entities to `SQLAlchemy` models, generate `Alembic` migrations, and update the 308 service files to use asynchronous database sessions rather than `CacheDict`.
