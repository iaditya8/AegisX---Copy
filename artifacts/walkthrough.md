# Walkthrough — Sprint 11: AI Security Copilot Framework

In this sprint, we implemented the advisory AI Security Copilot layer to support explanation services for assets, findings, and executive posture reports.

## Changes Made

### 1. Domain Entities & Schemas
- Created [copilot_response_schema.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/domain/entities/copilot_response_schema.py) defining strict Pydantic schemas:
  - `AssetExplanationSchema`: validates summary, risk analysis, and priority reasons.
  - `FindingExplanationSchema`: validates summary, impact, priority, and investigation guidance.
  - `ExecutiveSummarySchema`: validates executive summary, top risks, and notable changes.

### 2. Core Copilot Services
- Created [ai_guardrails.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_guardrails.py): Sanitizes context objects recursively to redact credential keys and Basic/Bearer strings.
- Created [ai_context_builder.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_context_builder.py): Collates asset, finding, and executive posture contexts under version `"1.0"`.
- Created [ai_prompt_builder.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_prompt_builder.py): Formats prompts to enforce strict raw JSON responses without markdown code fences.
- Created [ai_provider.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_provider.py) & [openai_provider.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/openai_provider.py): Standard HTTPX provider with timeouts and retries.
- Created [ai_provider_registry.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_provider_registry.py): Resolves the active provider dynamically.
- Created [ai_response_validator.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_response_validator.py): Performs schema enforcement.
- Created [ai_rate_limit_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_rate_limit_service.py): sliding rolling-window rate-limiter (Admin: 1000/hr, Operator: 250/hr).
- Created [ai_cache_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_cache_service.py): in-memory cache with 1-hour TTL and cascading invalidation.
- Created [ai_audit_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_audit_service.py): records prompt and response SHA-256 hashes in `audit_logs`.
- Created coordinating services:
  - [asset_copilot_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/asset_copilot_service.py)
  - [finding_copilot_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/finding_copilot_service.py)
  - [executive_copilot_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/executive_copilot_service.py)

### 3. API Routing
- Created [copilot.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/api/v1/routers/copilot.py) exposing:
  - `GET /api/v1/copilot/assets/{id}`
  - `GET /api/v1/copilot/findings/{id}`
  - `GET /api/v1/copilot/executive`
- Registered the router in [main.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/main.py).

### 4. Integration & Invalidation Cascades
- Updated [report_cache_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/report_cache_service.py) to cascade clear entries inside `AICacheService`.
- Updated [worker.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/infrastructure/celery/worker.py) to cascade invalidations after scan task step completion.

## Testing & Verification (Sprint 11)
All 182 test cases pass successfully:
```powershell
backend\tests\integration\test_copilot.py ..........                     [100%]
============================= 10 passed in 0.08s ==============================
```

---

# Walkthrough — Sprint 12: Exposure Decision Support Platform

In this sprint, we enhanced AegisX from an Exposure Intelligence and AI Advisory platform into a comprehensive Exposure Decision Support Platform. The platform provides deterministic, rule-based recommendation and prioritization capabilities to help security analysts prioritize assets, findings, technologies, and products based on risk and context.

## Changes Made

### 1. Domain Entities & Schemas
- Created [recommendation.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/domain/entities/recommendation.py) defining:
  - `RecommendationType` and `RecommendationPriority` Enums.
  - `RecommendationResponse`, `PriorityRankingResponse`, `InvestigationGuidanceResponse`, and `RecommendationSnapshotResponse` Pydantic models.

### 2. Core Service Layer & Engines
- Created [priority_factor_registry.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/priority_factor_registry.py): Maps context features to weights (critical_finding: 30, high_risk_asset: 25, internet_exposed: 20, rediscovered_finding: 15, high_criticality: 10).
- Created [prioritization_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/prioritization_service.py): Ranks assets, findings, technologies, and products on a normalized 0-100 scale.
- Created [recommendation_rules_registry.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/recommendation_rules_registry.py): Maps states to remediation rule types and priorities.
- Created [recommendation_fingerprint_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/recommendation_fingerprint_service.py): Generates stable SHA-256 fingerprints to ensure stability across recomputations.
- Created [recommendation_snapshot_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/recommendation_snapshot_service.py): Caches recommendation counts and priorities per asset in-memory.
- Created [recommendation_history_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/recommendation_history_service.py): Records recommendation life-cycle events, emits priority change alerts, and calculates aging in days.
- Created [investigation_assistance_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/investigation_assistance_service.py): Provides structured steps for investigating findings and assets.
- Created [recommendation_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/recommendation_service.py): Coordinates generation of asset and finding remediation options.

### 3. Integrations & Prompt Enforcements
- Updated `AIContextBuilder` to inject recommendations and snapshot details into the context.
- Modified `AIPromptBuilder` prompts with strict constraints instructing the LLM to act strictly as an explanation layer for deterministic recommendations, preventing arbitrary action generation or priority overriding.
- Integrated event-driven snapshot recomputations into the scan worker `worker.py`, risk snapshot changes, correlation updates, and finding processes.

### 4. API Routing
- Created [recommendations.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/api/v1/routers/recommendations.py) to expose endpoints for recommendations, priorities, rankings, and guidance with full RBAC and scope checks.

## Testing & Verification (Sprint 12)
All 194 test cases pass successfully:
```powershell
====================== 194 passed, 67 warnings in 13.23s ======================
```
- Integration tests in [test_recommendations.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/tests/integration/test_recommendations.py) fully verify deduplication, priority events, aging preservation, ranking, and API permission layers.

Compliance checks with Ruff and Black are passing cleanly.

---

# Walkthrough — Sprint 13: Remediation Intelligence & Workflow Management

In this sprint, we implemented the **Remediation Intelligence & Workflow Management** capabilities. This extends the advisory recommendations into an actionable, tracked remediation lifecycle. It supports owner assignment, strict state machine validations, SLA tracking, exception overriding with justifications, history logging, and real-time state count snapshot caching per asset.

## Changes Made

### 1. Domain Entities & Schemas
- Created [remediation.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/domain/entities/remediation.py) defining:
  - `RemediationStatus` and `RemediationHistoryType` Enums.
  - `RemediationResponse`, `RemediationHistoryResponse`, and `RemediationSnapshotResponse` Pydantic models.

### 2. Core Service Layer & Lifecycle Engines
- Created [remediation_sla_registry.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/remediation_sla_registry.py): Maps priorities to standard SLA remediation durations (`CRITICAL`: 7 days, `HIGH`: 30 days, `MEDIUM`: 60 days, `LOW`: 90 days).
- Created [sla_monitoring_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/sla_monitoring_service.py): Dynamically calculates target due dates and detects SLA breaches/compliance status.
- Created [remediation_aging_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/remediation_aging_service.py): Monitors remediation ages and computes overdue metrics.
- Created [remediation_history_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/remediation_history_service.py): Logs comprehensive event histories including creation, state transitions, ownership changes, and exceptions.
- Created [workflow_event_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/workflow_event_service.py): Emits typed workflow events through SQLALchemy databases.
- Created [exception_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/exception_service.py): Coordinates exception status overrides (`ACCEPTED_RISK`, `FALSE_POSITIVE`, `DEFERRED`) with reason details, audit logs, and approval tracking.
- Created [remediation_snapshot_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/remediation_snapshot_service.py): Formulates per-asset counts of active and archived remediations, rebuildable instantly on-demand.
- Created [remediation_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/remediation_service.py): Orchestrates creation, assignment, transition validation, and recommendation sync.

### 3. API Routing
- Created [remediations.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/api/v1/routers/remediations.py) exposing:
  - `POST /api/v1/remediations/{id}/assign` - Assignment of remediations.
  - `POST /api/v1/remediations/{id}/transition` - Validation and status update.
  - `POST /api/v1/remediations/{id}/exception` - Applying exception policies.
  - `GET /api/v1/remediations/{id}/history` - History log retrieval.
  - `GET /api/v1/remediations/asset/{asset_id}/snapshot` - Snapshot count retrieval.
- Registered the router in [main.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/main.py).

### 4. Integrations
- Hooked celery worker scan tasks in [worker.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/infrastructure/celery/worker.py) to sync recommendations and generate auto-remediations.
- Updated [ai_context_builder.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/ai_context_builder.py) to dynamically enrich LLM contexts with remediation snapshot details.

## Testing & Verification (Sprint 13)
All 202 test cases pass successfully:
```powershell
====================== 202 passed, 67 warnings in 13.04s ======================
```
- Integration tests in [test_remediation.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/tests/integration/test_remediation.py) fully verify auto-remediation, identity preservation, terminal states, API/scope RBAC blocking, and LLM context injections.
- Compliance checks with Ruff and Black are passing cleanly.

---

# Walkthrough — Sprint 14: Governance, Risk Acceptance & Compliance Intelligence

In this sprint, we implemented the **Governance, Risk Acceptance & Compliance Intelligence** capabilities. This extends the platform with governance evaluations, risk acceptance lifecycles, compliance control mappings, drift detection, and platform-wide governance snapshots.

## Changes Made

### 1. Domain Entities & Schemas
- Created [governance.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/domain/entities/governance.py) defining:
  - `GovernanceStatus`, `ComplianceSeverity`, and `RiskAcceptanceStatus` Enums.
  - `RiskAcceptanceResponse`, `ComplianceControlResponse`, and `GovernanceSnapshotResponse` Pydantic models.

### 2. Core Service Layer & Governance Engines
- Created [compliance_control_registry.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/compliance_control_registry.py): Maps finding and event rules to standard compliance controls (`VULN-001`, `EXP-001`, `OPS-001`, `GOV-001`).
- Created [risk_acceptance_registry.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/risk_acceptance_registry.py): Maps severities to risk acceptance durations (`CRITICAL`: 30, `HIGH`: 60, `MEDIUM`: 90, `LOW`: 180 days).
- Created [compliance_mapping_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/compliance_mapping_service.py): Evaluates open ports and findings to determine control compliance and link affected assets.
- Created [risk_acceptance_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/risk_acceptance_service.py): Manages risk acceptance lifecycles (accept, revoke, expire) and enforces transition reverts for remediations.
- Created [governance_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/governance_service.py): Provides read-only platform-wide, asset-specific, and finding-specific posture evaluations.
- Created [governance_snapshot_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/governance_snapshot_service.py): Caches platform-wide status metrics in-memory, auto-updating on modifications.
- Created [compliance_drift_service.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/services/compliance_drift_service.py): Compares states against historical compliance baselines and triggers workflow events / audit logs on drift.

### 3. API Routing
- Created [governance.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/api/v1/routers/governance.py) exposing:
  - `GET /api/v1/governance/assets/{id}` - Retrieve asset governance status.
  - `GET /api/v1/governance/findings/{id}` - Retrieve finding governance status.
  - `GET /api/v1/governance/summary` - Retrieve platform-wide summary metrics.
  - `GET /api/v1/governance/non-compliant-assets` - List non-compliant assets (filtered by ownership).
  - `GET /api/v1/governance/non-compliant-findings` - List non-compliant findings (filtered by ownership).
  - `GET /api/v1/governance/accepted-risks` - List active risk acceptances.
  - `POST /api/v1/governance/accept-risk` - Accept risk for a recommendation footprint (Admin only).
  - `POST /api/v1/governance/revoke-risk` - Revoke a risk acceptance (Admin only).
- Registered the router in [main.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/main.py).

### 4. Integrations
- Integrated Celery worker scan tasks in [worker.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/src/infrastructure/celery/worker.py) to refresh governance snapshots and run compliance drift checks dynamically.
- Integrated `AIContextBuilder` to inject asset, finding, and executive governance fields into LLM prompts.

## Testing & Verification (Sprint 14)
All 218 test cases pass successfully:
```powershell
====================== 218 passed, 67 warnings in 13.66s ======================
```
- Integration tests in [test_governance.py](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/backend/tests/integration/test_governance.py) fully verify risk acceptance logic, automatic expiration, revocation, SLA breach transitions, compliance control mappings, drift detection, AI context injection, and role-based access control.
- Compliance checks with Ruff and Black pass cleanly.
