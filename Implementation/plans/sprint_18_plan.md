# Sprint 18 — Implementation Plan

> **Paste your implementation plan for Sprint 18 below this line.**
> Delete this placeholder text when adding your content.

Sprint 18 Implementation Plan: Case Management & Evidence Chain-of-Custody Intelligence

AegisX will be transformed from an Incident Management Platform into a Case Management & Evidence Intelligence Platform. Sprint 18 introduces case lifecycle management, chain-of-custody tracking, evidence repositories, evidence integrity verification, analyst handoff workflows, investigation packaging, and executive case summaries.

User Review Required

[!IMPORTANT]Advisory-Only AI: The AI Security Copilot remains strictly advisory. It can summarize cases and verify evidence chains but is physically blocked from mutating case states, evidence, custody, or assignments.

In-Memory Operations: Case management, evidence, and custody tracking utilize in-memory registries and stores to avoid database migrations, preserving backward compatibility and mirroring existing architectural patterns.

Scope Filtering & RBAC: Operations on cases and evidence are subject to existing RBAC. Standard operators are restricted to cases tied to assets within their defined scopes.

Proposed Changes

Domain Models

[NEW] case.py

Create domain definitions for case and evidence modeling:

CaseSeverity(str, Enum): LOW, MEDIUM, HIGH, CRITICAL

CaseStatus(str, Enum): OPEN, ACTIVE, UNDER_REVIEW, ESCALATED, RESOLVED, CLOSED

EvidenceStatus(str, Enum): COLLECTED, VERIFIED, TRANSFERRED, ARCHIVED

ChainOfCustodyAction(str, Enum): CREATED, COLLECTED, VERIFIED, TRANSFERRED, ACCESSED, ARCHIVED

CaseResponse: Pydantic model for Case representation (case_id, case_fingerprint, title, description, severity, status, owner, created_at, updated_at, incident_ids).

EvidenceResponse: Pydantic model for Evidence representation (evidence_id, case_id, source_entity, source_id, integrity_hash, status, collected_by, collected_at).

ChainOfCustodyEntry: Pydantic model for custody timeline (entry_id, evidence_id, action, actor, timestamp, notes, integrity_verified).

CaseHistoryEntry: Pydantic model containing case_id, timestamp, event_type, details.

Registries & Fingerprinting

[NEW] case_severity_registry.py

Maps underlying incident/alert severity combinations to case severity deterministically, ensuring that case severity correctly reflects the maximum severity of contained events.

[NEW] case_fingerprint_service.py

Generates stable, deterministic fingerprints: SHA256(incident_ids, alert_ids, asset_ids).

Ensures the fingerprint remains stable across ownership changes, transitions, and evidence collection.

Case Synchronization Rule: Rerunning processing that generates the same fingerprint must update existing cases instead of creating new ones.

Case Fingerprint Stability Rule: The case fingerprint must remain stable across ownership changes, evidence collection/verification, custody transfers, investigation updates, analyst notes, review transitions, escalations, resolution, and closure. The fingerprint may only change when incident_ids, alert_ids, or asset_ids change. Do NOT include status, owner, timestamps, evidence ids, custody entries, or investigation entries in the calculation. This prevents duplicate case creation.

Core Services

[NEW] case_history_service.py

Keeps track of all state transitions and logs historical records.

Case History Preservation Rule: Case history entries are immutable. Existing history records must never be modified or deleted. Must survive case closure, escalation, and snapshot rebuilds.

[NEW] evidence_service.py

Manages evidence records attached to cases, representing collected data and logs.

Evidence Integrity Verification: Generates and verifies integrity_hash to prove evidence has not been tampered with since collection.

Evidence Preservation Rule: Evidence records are immutable historical artifacts. After collection, integrity_hash, collected_at, collected_by, source_entity, and source_id cannot change. Evidence may transition status (COLLECTED -> VERIFIED -> TRANSFERRED -> ARCHIVED), but the underlying evidence record itself must remain immutable to preserve forensic continuity.

Evidence Fingerprint Stability Rule: Evidence identity is determined by SHA256(source_entity, source_id, integrity_hash). The fingerprint must remain stable across verification, custody transfers, access events, status transitions, assignment changes, case escalation, and closure. It may only change if source_entity, source_id, or integrity_hash changes. This prevents the creation of duplicate evidence records after transitions, preserving chain-of-custody continuity.

[NEW] custody_service.py

Tracks the chain of custody for all evidence.

Chain of Custody Append-Only Rule: Custody entries are immutable. Every evidence transfer or access appends to the timeline. Custody chains must be preserved even after the case is closed.

Archived Evidence Enforcement: ARCHIVED is terminal. Archived evidence cannot be modified, transferred, recollected, or reassigned (only read operations allowed). A new evidence record may only exist if the source or hash changes, mirroring the enforcement for REMEDIATED, SUPPRESSED, and CLOSED states.

[NEW] case_evidence_correlation_service.py

Dynamically correlates evidence attached to cases, tracking the relationships between incidents, evidence, and overarching cases.

[NEW] case_service.py

Core workflow transitions and case store. Implements the case state machine:

OPEN -> ACTIVE

ACTIVE -> UNDER_REVIEW or ESCALATED

UNDER_REVIEW -> RESOLVED or ACTIVE (if returned)

ESCALATED -> ACTIVE

RESOLVED -> CLOSED

CLOSED -> terminal state (no transitions allowed). Enforce Closed Terminal Enforcement.

Synchronizes incidents into cases deterministically.

Evidence Identity Preservation Rule: If evidence synchronization runs multiple times with the same evidence hash, same source entity, and same source id, DO NOT create new evidence. Preserve evidence_id, custody history, verification history, and timestamps. Only update mutable metadata.

[NEW] case_snapshot_service.py

Memory-cached case statistics.

Case Snapshot Consistency: Snapshots are caches. If missing, corrupted, or deleted, they must rebuild dynamically from active case records via get_snapshot() and generate_snapshot().

Integrations

[MODIFY] worker.py

In workflow scan completion step, invoke CaseService.sync_cases(db) gracefully wrapped in exception handling.

[MODIFY] ai_context_builder.py

Inject case_summary, case_status, case_owner, case_evidence, and chain_of_custody into prompt contexts.

[MODIFY] ai_prompt_builder.py

Embed advisor-only constraints restricting the AI Security Copilot from performing mutating actions on cases, evidence, or custody chains.

API Gateway

[NEW] cases.py

Exposes REST endpoints:

GET /api/v1/cases

GET /api/v1/cases/{id}

POST /api/v1/cases/{id}/assign

POST /api/v1/cases/{id}/activate

POST /api/v1/cases/{id}/review

POST /api/v1/cases/{id}/resolve

POST /api/v1/cases/{id}/close

GET /api/v1/cases/{id}/evidence

POST /api/v1/cases/{id}/evidence

GET /api/v1/cases/{id}/custody

POST /api/v1/cases/{id}/transfer

GET /api/v1/cases/{id}/timeline

[MODIFY] main.py

Include and mount the new cases router under /api/v1.

Verification Plan

Automated Tests

Execute integration tests:

.venv\Scripts\pytest backend/tests/integration/test_cases.py

Includes test_case_auto_creation(), test_case_fingerprint_stability(), test_case_identity_preserved_after_escalation().

Includes test_case_closed_terminal_enforcement(), test_case_snapshot_rebuild_consistency().

Includes test_evidence_integrity_verification(), test_evidence_integrity_failure_event().

Includes test_chain_of_custody_append_only(), test_chain_of_custody_preserved_after_case_closure().

Includes test_case_history_preserved_after_closure(), test_case_sync_preserves_identity().

Includes test_ai_context_case_injection(), test_rbac_case_scope_validation().

Includes test_evidence_identity_preserved_after_verification(), test_archived_evidence_terminal_enforcement(), test_evidence_snapshot_rebuild_consistency().

Includes test_case_fingerprint_stability_after_evidence_collection().

Includes test_evidence_fingerprint_stability_after_transfer().

We will implement 30+ integration tests covering creation, deduplication, identity preservation, state machine rules, evidence integrity, chain-of-custody, and RBAC. We will maintain code coverage >= 85%.

Manual Verification

Verify that standard operators are restricted from retrieving or mutating cases involving assets outside their allowed scopes.