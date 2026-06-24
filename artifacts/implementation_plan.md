# Implementation Plan — Sprint 14: Governance, Risk Acceptance & Compliance Intelligence

This sprint transforms AegisX from a Remediation Intelligence Platform into a **Governance, Risk Acceptance & Compliance Intelligence Platform**. It introduces governance evaluation, compliance mappings, risk acceptance lifecycle management, drift detection, snapshot caching, AI context enrichments, and REST endpoints for compliance tracking.

## User Review Required

> [!IMPORTANT]
> Just like remediations, all risk acceptance records and governance snapshots will be managed **strictly in-memory** to remain compatible with the database schema constraints.
>
> Only users with the `admin` role are authorized to call `accept-risk` and `revoke-risk` endpoints.

## Open Questions

> [!IMPORTANT]
> **Question 1**: Under Sprint 13 rules, `ACCEPTED_RISK` is a terminal and immutable state in the `RemediationService` state machine. However, in Sprint 14, risk acceptances can expire or be revoked. 
> 
> *Proposed Solution*: When a risk acceptance expires or is revoked, we will update the remediation status back to `OPEN` (or `IN_PROGRESS`), bypassing the terminal validation rule specifically for administrative state reset, so that compliance controls reflect the failure properly. Do you approve this transition behavior?

## Proposed Changes

---

### Core Domain Models

#### [NEW] [governance.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/domain/entities/governance.py)
Defines the Pydantic schemas and Enums for the governance layer:
- `GovernanceStatus` Enum: `COMPLIANT`, `NON_COMPLIANT`, `ACCEPTED_RISK`, `UNDER_REVIEW`, `EXCEPTION_ACTIVE`
- `ComplianceSeverity` Enum: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- `RiskAcceptanceStatus` Enum: `ACTIVE`, `EXPIRING`, `EXPIRED`, `REVOKED`
- `RiskAcceptanceResponse`: Represents risk acceptance details (acceptance_id, asset_id, finding_id, recommendation_id, recommendation_fingerprint, approved_by, approved_at, expiration_date, status, reason).
- `ComplianceControlResponse`: Represents compliance control failures and mappings.
- `GovernanceSnapshotResponse`: Represents posture summary statistics (compliant_assets, non_compliant_assets, accepted_risks, expired_acceptances, exception_count, sla_breaches).

---

### Mappings & Registries

#### [NEW] [compliance_control_registry.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/compliance_control_registry.py)
- Maps risk/finding events to standard compliance controls:
  - `critical_vulnerability` -> `VULN-001`
  - `internet_exposed_admin_service` -> `EXP-001`
  - `sla_breach` -> `OPS-001`
  - `accepted_risk` -> `GOV-001`

#### [NEW] [risk_acceptance_registry.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/risk_acceptance_registry.py)
- Maps finding severity to default risk acceptance duration in days:
  - `CRITICAL` -> 30 days
  - `HIGH` -> 60 days
  - `MEDIUM` -> 90 days
  - `LOW` -> 180 days

---

### Core Governance Services

#### [NEW] [governance_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/governance_service.py)
- Read-only service that evaluates compliance and governance states:
  - `evaluate_asset_governance(db, asset_id)`: Checks asset findings, active remediations, exceptions, and SLA compliance.
  - `evaluate_finding_governance(db, finding_id)`: Determines compliance status for a specific finding.
  - `evaluate_platform_governance(db)`: Returns organization-wide compliance summary.
  - `get_non_compliant_assets(db)`: Retrieves assets failing any control mappings.
  - `get_non_compliant_findings(db)`: Retrieves findings failing any controls.

#### [NEW] [risk_acceptance_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/risk_acceptance_service.py)
- Handles risk acceptance state lifecycle:
  - `accept_risk()`: Registers in-memory acceptance, updates remediation status to `ACCEPTED_RISK` via `ExceptionService`, and triggers audit log / workflow events.
  - `revoke_risk()`: Revokes a risk acceptance, reverts remediation status, and refreshes snapshots.
  - `expire_risk()`: Transitions an active risk acceptance to `EXPIRED` status, generating `risk_acceptance.expired` events.
  - `get_active_acceptances()` / `get_expiring_acceptances()`: Filtered list retrieval.

#### [NEW] [compliance_mapping_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/compliance_mapping_service.py)
- Maps active findings, recommendations, and remediations to standard compliance controls (`ComplianceControlResponse`).

#### [NEW] [governance_snapshot_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/governance_snapshot_service.py)
- Caches overall compliant assets, non-compliant assets, accepted risks, expired acceptances, exception counts, and SLA breaches. Rebuilds from active governance state if cache is missing.

#### [NEW] [compliance_drift_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/compliance_drift_service.py)
- Analyzes transition drift (e.g., `Compliant -> Non-Compliant`, `Within SLA -> Breached`, `Accepted Risk -> Expired`) and fires corresponding workflow events.

---

### Routing & Integrations

#### [NEW] [governance.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/api/v1/routers/governance.py)
- Exposes compliance endpoints with RBAC controls (Admin-only for mutations):
  - `GET /api/v1/governance/assets/{id}`
  - `GET /api/v1/governance/findings/{id}`
  - `GET /api/v1/governance/summary`
  - `GET /api/v1/governance/non-compliant-assets`
  - `GET /api/v1/governance/non-compliant-findings`
  - `GET /api/v1/governance/accepted-risks`
  - `POST /api/v1/governance/accept-risk`
  - `POST /api/v1/governance/revoke-risk`

#### [MODIFY] [main.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/main.py)
- Register the new `governance_router`.

#### [MODIFY] [worker.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/infrastructure/celery/worker.py)
- Refreshes governance snapshots dynamically when recommendations/remediations/exceptions change or SLA breaches occur.

#### [MODIFY] [ai_context_builder.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_context_builder.py)
- Injects governance details (`governance_status`, `accepted_risks`, `expired_acceptances`, `compliance_controls`, `sla_breaches`) into asset, finding, and executive posture contexts.

#### [MODIFY] [asset_copilot_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/asset_copilot_service.py)
#### [MODIFY] [finding_copilot_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/finding_copilot_service.py)
#### [MODIFY] [executive_copilot_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/executive_copilot_service.py)
- Updates LLM prompt builders to enforce explanation-only rules for deterministic governance outcomes.

---

## Verification Plan

## Automated Tests
- Create `backend/tests/integration/test_governance.py` containing:
  - `test_risk_acceptance_creation`: Validates acceptance creation, model structures, workflow events, and audit logs.
  - `test_risk_acceptance_expiration`: Assures transition to `EXPIRED` status triggers updates and workflow events.
  - `test_risk_acceptance_revocation`: Verifies role authorization and cleanup of remediation states.
  - `test_asset_governance_status`: Verifies compliant vs non-compliant status evaluation.
  - `test_finding_governance_status`: Evaluates compliance mappings on individual findings.
  - `test_non_compliant_detection`: Validates retrieval of non-compliant assets/findings.
  - `test_compliance_control_mapping`: Assures deterministic mappings to standard controls.
  - `test_control_failure_detection`: Detects when an asset/finding breaches a control.
  - `test_control_restoration`: Confirms compliance recovery when vulnerabilities are patched.
  - `test_governance_snapshot_generation`: Validates cached statistics format and consistency.
  - `test_governance_snapshot_rebuild_consistency`: Tests dynamic rebuild of cached state.
  - `test_governance_drift_detection`: Simulates changes leading to drift events.
  - `test_sla_breach_governance_transition`: Tests drift from compliant to non-compliant when SLA is breached.
  - `test_ai_governance_context_injection`: Validates presence of governance statistics in AI prompt contexts.
  - `test_governance_admin_only_risk_acceptance`: Blocks operators and readers from accepting/revoking risks.
  - `test_governance_scope_restrictions`: Verifies scope checks on assets/findings.
- Run tests:
  ```powershell
  .venv\Scripts\pytest
  ```
- Formatting & Linting checks:
  ```powershell
  .venv\Scripts\ruff check backend/
  .venv\Scripts\black --check backend/
  ```

### Manual Verification
- None required; full verification achieved via integration tests.
