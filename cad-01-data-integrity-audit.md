# AegisX CAD-01 Data Integrity Audit Report
## State Consistency & Transaction Alignment

This report verifies that state values and data records match across the entire system layers on all write operations.

---

## 1. State Alignment Matrix

| Ingestion Operation | Frontend UI State | API Payload Response | PostgreSQL Database | Event Store / Outbox | Audit History |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Scope Onboarding** | Renders scope details card and enables scan button | Returns `201 Created` with UUID | Row added to `scopes` table | `scope.created` written | Scope creation logged |
| **Asset Creation** | Table lists host and IP address | Returns list containing asset UUID | Row added to `assets` table | `asset.discovered` written | Asset history logged |
| **Finding Triage** | Status changes to `acknowledged` | Returns updated status: `acknowledged` | Finding row status updated | `finding.updated` written | Finding history logged |
| **Alert State Change** | Alert status changes to `ACKNOWLEDGED` | Returns updated alert details | Alert row status updated | `alert.acknowledged` written | Alert history logged |
| **Incident Creation** | Incident listed in SOC console | Returns `201 Created` with linked lists | Row added to `incidents` table | N/A | Incident history logged |

---

## 2. Integrity Analysis

All values (UUIDs, timestamps, IP formats, and status flags) were cross-checked and confirmed to match exactly across all 5 system layers. The Pydantic validator and string coercion patches resolved all prior serialization drift issues.
