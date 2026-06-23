# Sprint 31 — Walkthrough

> **Paste your walkthrough for Sprint 31 below this line.**
> Delete this placeholder text when adding your content.

Sprint 31 — Governance, Risk & Compliance (GRC) Intelligence — Walkthrough

Overview

Sprint 31 transitions AegisX into a Governance, Risk & Compliance (GRC) Intelligence Platform. This release introduces compliance frameworks, control mappings, compliance scoring, audit readiness, gap tracking, drift detection, and assessments.

Files Created & Modified in Sprint 31

1. Domain Model

governance_risk_compliance.py [NEW] — Defines enums (ComplianceSeverity, ComplianceStatus, FrameworkType) and models (ComplianceAssessmentResponse, FrameworkControlResponse, ComplianceEvidenceResponse, ComplianceGapResponse, ComplianceHistoryEntry).

2. Registries

compliance_framework_registry.py [NEW] — Registers pre-seeded framework objects (ISO27001, NIST CSF, NIST 800-53, CIS, SOC2, PCI DSS).

control_mapping_registry.py [NEW] — Maps Sprint 24/25 controls, exposures, and risks to GRC compliance frameworks.

compliance_severity_registry.py [NEW] — Maps compliance impact severities.

3. Core Services

Service

Purpose / Implementation Details

compliance_fingerprint_service.py [NEW]

Generates stable SHA-256 fingerprints based on framework, scope, and normalized assessment name.

compliance_history_service.py [NEW]

Logs GRC history events in an append-only format.

framework_mapping_service.py [NEW]

Maps findings, exposures, and controls to framework nodes.

compliance_scoring_service.py [NEW]

Evaluates compliance readiness and scores.

audit_readiness_service.py [NEW]

Computes compliance completeness and maturity levels.

compliance_gap_service.py [NEW]

Documents missing controls or evidence gaps.

compliance_drift_service.py [MODIFY]

Captures drift changes and merges asset, finding, and expiration drift from Sprints 1-29.

compliance_snapshot_service.py [NEW]

Non-authoritative compliance snapshots in cache.

governance_risk_compliance_service.py [NEW]

Coordinates GRC assessment workflows, lifecycle transitions, and identity preservation.

4. Integrations

worker.py [MODIFY] — Runs periodic GRC synchronization and scoring in a crash-safe task block.

ai_context_builder.py [MODIFY] — Injects compliance scores and gaps into AI context.

ai_prompt_builder.py [MODIFY] — Restricts AI mutations to GRC assessments.

main.py [MODIFY] — Registers API router /api/v1/governance-risk-compliance.

governance_risk_compliance.py [NEW] — Router exposing endpoint routes with scope-based RBAC enforcement.

Architectural Constraints & Hardening Rules

1. Compliance Assessment Terminal State Rule

CLOSED is a terminal state for GRC assessments. Once closed, synchronization, worker runs, compliance scoring, and snapshot rebuilds cannot transition the assessment back to any active status (e.g. ACTIVE, IN_REVIEW).

2. Compliance Evidence Preservation Rule

Evidence records are authoritative compliance artifacts and must never be modified during scoring, framework mapping, drift processing, or snapshot rebuilds. Evidence changes are restricted to explicit evidence management workflows.

3. Compliance History Preservation Rule

History entries are immutable and append-only. Only new events are appended, preventing any mutation, deletion, or reordering.

4. Compliance Scoring Determinism Rule

Compliance score, framework coverage, and audit readiness calculations must be deterministic. Identical inputs must always produce identical outputs.

Calculations must never mutate assessments, histories, evidence records, or snapshots.

5. Framework Mapping Preservation Rule

Framework mappings are derived read-only intelligence and must be deterministic and reproducible. Framework mapping calculations must never mutate compliance assessments, evidence, histories, or snapshots.

6. Compliance Snapshot Consistency Rule

Snapshots are cache-only, non-authoritative, and rebuildable. Missing or corrupted snapshots trigger a transparent rebuild from GRC source data.

Test Results

123/123 integration tests passed in test_governance_risk_compliance.py.
