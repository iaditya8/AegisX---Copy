# Sprint 31 — Implementation Plan

> **Paste your implementation plan for Sprint 31 below this line.**
> Delete this placeholder text when adding your content.

Implementation Plan - Sprint 31: Governance, Risk & Compliance (GRC) Intelligence

Transform AegisX from a Cyber Risk Quantification Intelligence Platform into a Governance, Risk & Compliance (GRC) Intelligence Platform.

User Review Required

[!IMPORTANT]

All compliance records, controls, assessments, policy mappings, evidence records, audit histories, and snapshots operate strictly in-memory.

Zero database migrations.

Zero external compliance platforms.

Zero external GRC integrations.

AI Security Copilot remains strictly advisory-only.

Architectural Constraints (Sprint 1–31 Compliance)

Registry-driven design: All GRC frameworks, control mappings, and severities must be validated against registries.

Deterministic fingerprinting: Assessment fingerprints must be generated using SHA-256 and remain stable.

Identity preservation: Syncs and updates must preserve the unique identifiers of assessments.

Terminal-state enforcement: CLOSED compliance assessments must never transition back to active states.

Immutable historical records: History entries must never be modified, deleted, or reordered.

Snapshot rebuild consistency: Snapshots are non-authoritative caches and must be fully rebuildable from active source GRC data.

In-memory storage only: Zero database migrations.

No external integrations: Zero external GRC or compliance platforms.

No breaking API changes: Keep all existing endpoints and routers backward compatible.

Full backward compatibility: Guarantee that all previous sprints (1-30) run without regression.

AI Advisory-only enforcement: Physically block the AI Security Copilot from executing any compliance mutations.

Lifecycle & Hardening Rules

Compliance Assessment Terminal State Rule

CLOSED is a terminal state.

Requirements:

synchronization cannot reopen CLOSED assessments

worker refresh cycles cannot reopen CLOSED assessments

control mapping updates cannot reopen CLOSED assessments

compliance scoring cannot reopen CLOSED assessments

drift processing cannot reopen CLOSED assessments

snapshot rebuilds cannot reopen CLOSED assessments

A new assessment may only be created if the fingerprint changes.

Compliance Synchronization Rule

If synchronization generates an identical fingerprint:

preserve assessment_id

preserve fingerprint

preserve created_at

preserve updated_at

preserve history

preserve evidence mappings

preserve framework mappings

Do not create duplicates.Do not create replacement records.Return the existing assessment.

Compliance Identity Preservation Rule

If synchronization generates an identical fingerprint:

preserve assessment_id

preserve fingerprint

preserve created_at

preserve history

preserve evidence mappings

preserve framework mappings

Do not create duplicates.

Compliance Evidence Preservation Rule

Evidence records are authoritative compliance artifacts.

Requirements:

never modify evidence records during scoring

never modify evidence records during framework mapping

never modify evidence records during drift processing

never modify evidence records during snapshot rebuilds

Evidence may only be changed through explicit evidence management workflows.

Derived compliance calculations are read-only.

Compliance History Preservation Rule

History entries are immutable.

Requirements:

never modify history

never delete history

never reorder history

History must survive:

worker refreshes

compliance scoring

framework remapping

drift processing

snapshot rebuilds

History is the authoritative audit trail.Only append new events.

Compliance Scoring Determinism Rule

Compliance calculations are derived intelligence.

Requirements:

compliance score calculations must be deterministic

framework coverage calculations must be deterministic

control effectiveness mappings must be deterministic

audit readiness calculations must be deterministic

Identical inputs must always produce identical outputs.

Calculations must never mutate:

assessments

histories

evidence records

snapshots

Calculations are read-only intelligence generation.

Framework Mapping Preservation Rule

Framework mappings are derived governance intelligence.

Requirements:

framework mapping calculations must be deterministic

framework mappings must be reproducible

identical inputs must always produce identical mappings

Framework mapping calculations must never mutate:

compliance assessments

evidence records

histories

snapshots

Framework mapping is read-only intelligence generation.

Compliance Snapshot Consistency Rule

Snapshots are:

cache-only

rebuildable

non-authoritative

If cache is:

missing

deleted

corrupted

generate_snapshot() and get_snapshot() must rebuild from source compliance intelligence.

No state may exist exclusively inside snapshots.Source compliance records remain authoritative.

Proposed Changes

Domain Models

[NEW] governance_risk_compliance.py

Define enums:

ComplianceSeverity (LOW, MEDIUM, HIGH, CRITICAL)

ComplianceStatus (ACTIVE, IN_REVIEW, COMPLIANT, NON_COMPLIANT, CLOSED)

FrameworkType (ISO27001, NIST_CSF, NIST_800_53, CIS_CONTROLS, SOC2, PCI_DSS)

Define Pydantic models:

ComplianceAssessmentResponse: Represents a compliance assessment.

FrameworkControlResponse: Represents framework controls mapped to assets/risks.

ComplianceEvidenceResponse: Mapped evidence files/hashes.

ComplianceGapResponse: Missing control/evidence gap reports.

ComplianceHistoryEntry: Historical audit trail entries.

Registries

[NEW] compliance_framework_registry.py

Pre-seeded: ISO27001, NIST_CSF, NIST_800_53, CIS_CONTROLS, SOC2, PCI_DSS.

[NEW] control_mapping_registry.py

Maps Sprint 25 Controls, Sprint 24 Security Posture, Sprint 23 Exposures, and Sprint 30 Quantified Risks to compliance frameworks.

[NEW] compliance_severity_registry.py

Maps compliance severity thresholds.

Fingerprinting

[NEW] compliance_fingerprint_service.py

Generates SHA256(framework_type, scope_id, normalized_assessment_name).

Fingerprint must remain stable across scoring, worker runs, evidence updates, drift checks, and snapshot rebuilds.

Core Services

[NEW] compliance_history_service.py

Immutable history audit logs. Tracks: CREATED, CONTROL_MAPPED, EVIDENCE_ADDED, GAP_IDENTIFIED, SCORE_CHANGED, DRIFT_DETECTED, CLOSED.

[NEW] governance_risk_compliance_service.py

Handles GRC creation, synchronization, status transitions, and gaps.

[NEW] framework_mapping_service.py

Maps controls, exposures, risks, findings, and program objectives to compliance frameworks.

[NEW] compliance_scoring_service.py

Calculates framework coverage, control coverage, evidence completeness, compliance readiness, and compliance score.

[NEW] audit_readiness_service.py

Calculates audit readiness metrics.

[NEW] compliance_gap_service.py

Tracks missing controls, missing evidence, and deficiencies.

[NEW] compliance_drift_service.py

Identifies GRC score/coverage shifts. Emits compliance.drift and compliance.score_changed.

[NEW] compliance_snapshot_service.py

Computes framework metrics and gap summaries in cache.

Integrations

[MODIFY] worker.py

Add GRC background tasks. Enforce safety blocks for each call.

Sprint 31 Worker Execution Order

GovernanceRiskComplianceService.sync_assessments()

FrameworkMappingService.calculate()

ComplianceScoringService.calculate()

AuditReadinessService.calculate()

ComplianceGapService.calculate()

ComplianceDriftService.process_drift()

ComplianceSnapshotService.generate_snapshot()

Failures in one service must not block others.

[MODIFY] ai_context_builder.py

Inject compliance summaries (compliance_summary, framework_coverage, compliance_score, audit_readiness, compliance_gap_summary, compliance_drift_summary) into all AI context builders.

[MODIFY] ai_prompt_builder.py

Add guardrails preventing mutations of GRC data by the AI Security Copilot.

[MODIFY] main.py

Register governance_risk_compliance API router.

API Gateway

[NEW] governance_risk_compliance.py

POST: /, /{id}/review, /{id}/compliant, /{id}/non-compliant, /{id}/close.

GET: /, /active, /frameworks, /gaps, /drift, /summary, /{id}.Enforces RBAC (admin, operator, reader) and scope isolation checks.

Verification Plan

Automated Tests

Implement 120+ integration tests in test_governance_risk_compliance.py.

Coverage target: >= 85% code coverage.

Sprint 31 Mandatory Test Cases

test_assessment_auto_creation()

test_assessment_fingerprint_stability()

test_assessment_identity_preservation()

test_assessment_duplicate_prevention()

test_assessment_review_transition()

test_assessment_compliant_transition()

test_assessment_non_compliant_transition()

test_assessment_close_transition()

test_assessment_terminal_state_enforcement()

test_closed_assessment_not_reactivated_by_sync()

test_closed_assessment_not_reactivated_by_worker()

test_closed_assessment_not_reactivated_by_snapshot()

test_closed_assessment_not_reactivated_by_drift()

test_closed_assessment_not_reactivated_by_remapping()

test_compliance_history_preserved()

test_compliance_history_immutable()

test_compliance_history_order_preserved()

test_framework_mapping_deterministic()

test_framework_control_mapping_consistency()

test_compliance_score_calculation()

test_framework_coverage_calculation()

test_control_effectiveness_mapping_read_only()

test_audit_readiness_calculation()

test_evidence_completeness_calculation()

test_compliance_gap_tracking()

test_compliance_drift_detection()

test_compliance_drift_clearing()

test_snapshot_rebuild_consistency()

test_snapshot_rebuild_after_cache_deletion()

test_snapshot_rebuild_after_cache_corruption()

test_snapshot_not_authoritative()

test_ai_context_compliance_injection()

test_ai_advisory_only_enforcement()

test_rbac_compliance_scope_validation()

test_worker_integration()

test_assessment_identity_preserved_after_worker_refresh()

test_assessment_identity_preserved_after_scoring_refresh()

test_assessment_identity_preserved_after_snapshot_rebuild()

test_assessment_identity_preserved_after_drift_processing()

Additional Coverage Areas

Registry validation (framework, severity, mappings).

Duplicate prevention mechanisms on GRC syncs.

History immutability checks across recalculations.

Drift event emissions and webhook simulation.

Scope bounds checking for multi-tenant isolation.

Snapshot cache destruction and auto-healing checks.

Audit evidence validation (hashes, formats).

Zero DB migration regression checks.

Run:

.venv\Scripts\pytest backend/tests/integration/test_governance_risk_compliance.py
.venv\Scripts\pytest

Deliverables

Upon completion provide:

1. Architecture Summary

Explain GRC lifecycle, calculations, mapping architectures, drift detection, and snapshots engine.

2. File Manifest

List of all new and modified files.

3. Testing Results

Pytest logs and metrics for the test suite.

4. Verification Summary

Confirm terminal state, history, snapshot, and AI advisory rules.

5. Backward Compatibility Statement

Guarantee zero migrations, zero regressions, and full compatibility with Sprints 1-30.

After creating the implementation plan:

STOP.

Wait for approval before implementation.