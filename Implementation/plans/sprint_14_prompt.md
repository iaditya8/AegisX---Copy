# Sprint 14 — Prompt (No Implementation Plan Available)

> **Paste your prompt for Sprint 14 below this line.**
> I will generate a full implementation plan from this prompt for your approval before implementing.
> Delete this placeholder text when adding your content.

sprint 14 prompt for implementation plan 14

Sprint 13 Approved

Begin Sprint 14.

Read:

Docs/03_Architecture.md
Docs/04_Database.md
Docs/05_API.md
Docs/07_AgentRules.md
Docs/09_CodingStandards.md

Implementation/BackendArchitecture.md
Implementation/RiskArchitecture.md

Act as:

Principal Security Architect
Principal Software Architect
Staff Backend Engineer
Governance Risk & Compliance Architect
Exposure Management Architect

Implement Sprint 14 only.

Sprint 14 Goal

Transform AegisX from a Remediation Intelligence Platform into a Governance, Risk Acceptance & Compliance Intelligence Platform.

Sprint 14 introduces:

Governance Evaluation
Risk Acceptance Lifecycle
Compliance Mapping
Governance Drift Detection
Compliance State Tracking
Governance Snapshots
Governance Intelligence APIs
Governance AI Context Enrichment

The goal is to answer:

Which risks have been formally accepted?

Which accepted risks are expiring?

Which assets are non-compliant?

Which findings are non-compliant?

Which controls are failing?

Where are governance gaps emerging?

What governance drift occurred recently?

What compliance issues require review?
Builds Directly On
Sprint 7 Asset Intelligence
Sprint 8 Vulnerability Intelligence
Sprint 9 Correlation & Risk Intelligence
Sprint 10 Reporting & Analytics
Sprint 11 AI Security Copilot
Sprint 12 Exposure Decision Support
Sprint 13 Remediation Intelligence
Becomes Foundation For
Sprint 15 Continuous Monitoring
Sprint 16 Distributed Scanning
Sprint 17 Multi-Tenant Operations
Sprint 18 Enterprise Operations
Sprint 19 Production Hardening
Do NOT Implement
Frontend

Dashboards

Ticketing

Jira Integration

Slack Integration

SOAR

Workflow Automation

New Scanners

Continuous Monitoring

Distributed Scanning

Multi-Tenant Architecture

Production Deployment

Compliance Report Exporting

Risk Score Modifications

Remediation Engine Replacement

Recommendation Engine Replacement
Mandatory Cross-Sprint Compatibility Validation

Before implementation review all prior sprint architecture.

Implementation MUST:

Reuse RecommendationService

Reuse RecommendationFingerprintService

Reuse RecommendationHistoryService

Reuse RemediationService

Reuse RemediationHistoryService

Reuse ExceptionService

Reuse WorkflowEventService

Reuse AuditService

Reuse AIContextBuilder

Reuse existing ownership validation patterns

Reuse snapshot rebuild patterns

Reuse cache refresh patterns

Implementation MUST NOT create:

Duplicate Risk Engines

Duplicate Remediation Engines

Duplicate Exception Systems

Duplicate Audit Systems

Duplicate Workflow Systems

Duplicate Ownership Systems

Duplicate Snapshot Frameworks

Extend architecture only.

Architectural Principles

Governance is layered on top of:

Findings

Risk Scores

Recommendations

Remediations

Exceptions

SLA Monitoring

Governance never replaces them.

Governance consumes them.

Governance evaluates them.

All governance outputs must be:

Deterministic

Explainable

Auditable

Reproducible

AI may explain governance.

AI may NOT create governance decisions.

Implement
Core Domain Models

Create:

backend/src/domain/entities/governance.py

Create:

class GovernanceStatus(str, Enum):
    COMPLIANT
    NON_COMPLIANT
    ACCEPTED_RISK
    UNDER_REVIEW
    EXCEPTION_ACTIVE

Create:

class ComplianceSeverity(str, Enum):
    LOW
    MEDIUM
    HIGH
    CRITICAL

Create:

class RiskAcceptanceStatus(str, Enum):
    ACTIVE
    EXPIRING
    EXPIRED
    REVOKED
RiskAcceptanceResponse

Must include:

{
  "acceptance_id": "...",
  "asset_id": "...",
  "finding_id": "...",
  "recommendation_id": "...",
  "recommendation_fingerprint": "...",
  "approved_by": "...",
  "approved_at": "...",
  "expiration_date": "...",
  "status": "ACTIVE",
  "reason": "..."
}
ComplianceControlResponse
{
  "control_id": "...",
  "control_name": "...",
  "status": "NON_COMPLIANT",
  "severity": "HIGH",
  "affected_assets": [],
  "affected_findings": []
}
GovernanceSnapshotResponse
{
  "compliant_assets": 0,
  "non_compliant_assets": 0,
  "accepted_risks": 0,
  "expired_acceptances": 0,
  "exception_count": 0,
  "sla_breaches": 0
}
Compliance Registry Layer

Create:

backend/src/services/compliance_control_registry.py

Centralize compliance mappings.

Example:

CONTROL_MAPPINGS = {
    "critical_vulnerability": "VULN-001",
    "internet_exposed_admin_service": "EXP-001",
    "sla_breach": "OPS-001",
    "accepted_risk": "GOV-001",
}

No hardcoded compliance logic.

Risk Acceptance Registry

Create:

backend/src/services/risk_acceptance_registry.py
RISK_ACCEPTANCE_DAYS = {
    "CRITICAL": 30,
    "HIGH": 60,
    "MEDIUM": 90,
    "LOW": 180
}

All expiration calculations must consume registry values.

Governance Service

Create:

backend/src/services/governance_service.py

Responsibilities:

evaluate_asset_governance()

evaluate_finding_governance()

evaluate_platform_governance()

get_non_compliant_assets()

get_non_compliant_findings()

Consumes:

Risk Snapshots
Recommendations
Remediations
Exceptions
SLA Monitoring

Produces:

GovernanceStatus

Read-only evaluation service.

Must never write state.

Risk Acceptance Service

Create:

backend/src/services/risk_acceptance_service.py

Responsibilities:

accept_risk()

revoke_risk()

expire_risk()

get_active_acceptances()

get_expiring_acceptances()

Requirements:

Reuse Sprint 13 ExceptionService

Reuse Ownership Validation

Track approved_by

Track approved_at

Track expiration_date

Track lifecycle status
Compliance Mapping Service

Create:

backend/src/services/compliance_mapping_service.py

Maps:

Findings

Recommendations

Remediations

to compliance controls.

Outputs:

ComplianceControlResponse
Governance Snapshot Service

Create:

backend/src/services/governance_snapshot_service.py

Track:

compliant_assets

non_compliant_assets

accepted_risks

expired_acceptances

exception_count

sla_breaches

Methods:

generate_snapshot()

update_snapshot()

get_snapshot()
Snapshot Consistency Requirement

Snapshots are cache only.

Never authoritative.

If cache missing:

generate_snapshot()

must rebuild from active governance state.

Follow:

CorrelationSnapshotService

RecommendationSnapshotService

RemediationSnapshotService

patterns.

Governance Drift Service

Create:

backend/src/services/compliance_drift_service.py

Detect:

Compliant -> Non-Compliant

Within SLA -> Breached SLA

Accepted Risk -> Expired

Exception Active -> Non-Compliant

Generate governance events.

Deterministic only.

Risk Acceptance Lifecycle

Implement:

ACTIVE
 ↓
EXPIRING
 ↓
EXPIRED

Rules:

Expiration cannot occur silently

Expiration must generate workflow event

Expiration must generate audit record

Expiration must update governance state

Expiration must refresh snapshots
Workflow Event Integration

Reuse WorkflowEventService.

Create events:

risk_acceptance.created

risk_acceptance.expiring

risk_acceptance.expired

risk_acceptance.revoked

governance.compliant

governance.non_compliant

compliance.control_failed

compliance.control_restored

Follow existing workflow event schema.

Audit Integration

Reuse AuditService.

Every governance mutation must create:

Audit Entry

Workflow Event

No duplicate audit system.

AI Security Copilot Integration

Modify:

backend/src/services/ai_context_builder.py

backend/src/services/asset_copilot_service.py

backend/src/services/finding_copilot_service.py

backend/src/services/executive_copilot_service.py

Inject:

{
  "governance_status": "...",
  "accepted_risks": [],
  "expired_acceptances": [],
  "compliance_controls": [],
  "sla_breaches": []
}
Hard AI Constraints

AI may:

Explain governance

Explain compliance failures

Explain accepted risks

Explain governance drift

AI may NOT:

Approve risk

Revoke risk

Modify governance state

Create compliance decisions

Governance decisions remain deterministic.

API Layer

Create:

backend/src/api/v1/routers/governance.py

Endpoints:

GET  /api/v1/governance/assets/{id}

GET  /api/v1/governance/findings/{id}

GET  /api/v1/governance/summary

GET  /api/v1/governance/non-compliant-assets

GET  /api/v1/governance/non-compliant-findings

GET  /api/v1/governance/accepted-risks

POST /api/v1/governance/accept-risk

POST /api/v1/governance/revoke-risk

Requirements:

Authentication

RBAC

Scope Ownership Validation

Only Admin may:

accept-risk

revoke-risk
Worker Integration

Modify:

backend/src/infrastructure/celery/worker.py

Refresh governance snapshots whenever:

Recommendation changes

Remediation changes

Exception changes

Risk score changes

SLA breach occurs

Must fail gracefully.

Must never interrupt scan execution.

Testing

Create:

backend/tests/integration/test_governance.py

Required Tests:

test_risk_acceptance_creation

test_risk_acceptance_expiration

test_risk_acceptance_revocation

test_asset_governance_status

test_finding_governance_status

test_non_compliant_detection

test_compliance_control_mapping

test_control_failure_detection

test_control_restoration

test_governance_snapshot_generation

test_governance_snapshot_rebuild_consistency

test_governance_drift_detection

test_sla_breach_governance_transition

test_ai_governance_context_injection

test_governance_admin_only_risk_acceptance

test_governance_scope_restrictions
Regression Requirements

Execute:

.venv\Scripts\pytest backend/tests/integration/test_governance.py

.venv\Scripts\pytest

.venv\Scripts\ruff check backend/

.venv\Scripts\black backend/

All Sprint 7–13 functionality must remain operational.

No existing tests may be modified solely to make Sprint 14 pass.

Deliverables

Generate:

task.md

walkthrough.md

implementation_summary.md

test_summary.md

Must include:

Governance Architecture

Risk Acceptance Lifecycle

Compliance Mapping Architecture

Governance Drift Detection Flow

Governance Snapshot Design

Workflow Event Flow

Audit Integration Flow

AI Governance Context Flow

API Examples

Verification Results
Stop Condition

Stop after Sprint 14 implementation and verification.

Do not begin Sprint 15.

Do not implement Continuous Monitoring.

Do not implement Distributed Scanning.

Do not implement Multi-Tenant Operations.

Only complete Sprint 14.