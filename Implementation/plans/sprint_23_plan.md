# Sprint 23 — Implementation Plan

> **Paste your implementation plan for Sprint 23 below this line.**
> Delete this placeholder text when adding your content.

Sprint 23: Exposure Management & Attack Surface Intelligence

Transform AegisX from a Purple Team & ATT&CK Validation Intelligence Platform into an Exposure Management & Attack Surface Intelligence Platform. Introduce Exposure Management, Attack Surface Intelligence, Asset Exposure Intelligence, External Exposure Intelligence, Misconfiguration Intelligence, Exposure Correlation Intelligence, Exposure Drift Detection, Exposure Prioritization Intelligence, Exposure Coverage Analytics, and Exposure Intelligence Snapshots.

User Review Required

[!IMPORTANT]Exposure Identity Preservation Rule:If a synchronization run generates the same exposure fingerprint SHA256(exposure_type, asset_id, normalized_target), preserve exposure_id, history, ownership, prioritization history, timestamps, and drift history. Do NOT create duplicate exposures. A new exposure may only be created if:

exposed asset changes

exposure type changes

exposure target changes

[!IMPORTANT]Exposure Terminal State Rule:Once an exposure transitions to CLOSED, it is terminal and non-reversible. Subsequent synchronization runs or snapshot rebuilds will not modify it, reopen it, or change its state.

[!WARNING]No external attack surface management (ASM) providers (such as Shodan, Censys, SecurityTrails, ZoomEye, leakage databases, etc.) will be integrated. The platform operates entirely offline, registry-driven, and in-memory using internal AegisX intelligence assets (Assets, Findings, Risks, Alerts, Incidents, Cases, Detections, IOCs, etc.).

Open Questions

[!NOTE]There are no open questions. All enums, models, services, transitions, and registry lists are defined explicitly by the architecture requirements.

Proposed Changes

Domain Models

[NEW] exposure.py

Define enums and response schemas:

ExposureSeverity: LOW, MEDIUM, HIGH, CRITICAL

ExposureStatus: OPEN, VALIDATED, ACCEPTED, MITIGATED, CLOSED

ExposureType: MISCONFIGURATION, EXTERNAL_SERVICE, EXPOSED_PORT, EXPOSED_CREDENTIAL, WEAK_CONTROL, DETECTION_GAP, ATTACK_SURFACE

ExposureResponse:

exposure_id: uuid.UUID

exposure_fingerprint: str

title: str

description: str

severity: ExposureSeverity

status: ExposureStatus

exposure_type: ExposureType

asset_id: uuid.UUID

owner: Optional[str]

risk_score: float

created_at: datetime

updated_at: datetime

ExposureHistoryEntry:

exposure_id: uuid.UUID

timestamp: datetime

event_type: str

details: str

ExposureFindingResponse:

finding_id: uuid.UUID

exposure_id: uuid.UUID

severity: ExposureSeverity

category: str

description: str

created_at: datetime

Registries

[NEW] exposure_type_registry.py

Validate supported exposure types.

[NEW] exposure_severity_registry.py

Standardize severity level resolution and mapping.

[NEW] attack_surface_registry.py

Pre-seed categories: WEB_APPLICATION, API, HOST, IDENTITY, EMAIL, CLOUD_RESOURCE, NETWORK_SERVICE.

Fingerprinting

[NEW] exposure_fingerprint_service.py

Generate fingerprint: SHA256(exposure_type, asset_id, normalized_target).

Exposure Fingerprint Stability Rule: Fingerprint remains stable across severity, status, ownership, prioritization, drift, and snapshot rebuild events. Changes only when exposure_type, asset_id, or target changes.

Core Services

[NEW] exposure_history_service.py

Append-only immutable log tracking: CREATED, VALIDATED, ACCEPTED, MITIGATED, CLOSED, PRIORITY_CHANGED, DRIFT_DETECTED.

Exposure History Preservation Rule: History is immutable, copy-safe (using deepcopy), never modified or deleted. Must survive mitigation, closure, sync, and snapshot rebuilds.

[NEW] exposure_service.py

Manage exposure creation, sync, validation, mitigation, closure.

State Machine: OPEN -> VALIDATED -> ACCEPTED or MITIGATED -> CLOSED.

Exposure Terminal State Rule: CLOSED status is terminal. Re-execution, re-opening, activation, worker sync, or snapshot updates cannot modify closed exposures.

Automatically scan current platform assets, ports, services, misconfigurations, detection gaps, and compliance accepts/findings during sync_exposures(db).

[NEW] attack_surface_service.py

Manage attack surface categorization and categorization mappings for assets.

Automatically maps assets to categories based on open ports/services (e.g., port 80/443 to WEB_APPLICATION).

[NEW] exposure_correlation_service.py

Correlate exposures against: Findings, Risks (RiskAcceptances), Alerts, Incidents, Cases, Hunts, and Purple Team findings.

Exposure Correlation Preservation Rule: Correlations are immutable and append-only.

[NEW] exposure_prioritization_service.py

Calculate risk_score, likelihood, and impact score. Priorities are calculated based on severity and asset criticality.

[NEW] exposure_drift_service.py

Detect drift events: NEW_EXPOSURE, EXPOSURE_REMOVED, SEVERITY_CHANGED, PRIORITY_CHANGED, ATTACK_SURFACE_CHANGED.

Emits exposure.drift and exposure.priority_changed workflow events.

[NEW] exposure_snapshot_service.py

Rebuildable cache containing total exposures, status counts, critical count, attack surface coverage, and organization risk score.

Exposure Snapshot Consistency Rule: Snapshot data is cache-only and must rebuild dynamically.

Integrations

[MODIFY] worker.py

Gracefully trigger Exposure sync, Attack Surface sync, Prioritization calculations, Drift processing, and Snapshot generation at the end of the Celery worker task execution chain.

[MODIFY] ai_context_builder.py

Inject exposure summary metrics, risk score, attack surface, drift, and priorities into asset, finding, incident, case, and executive contexts.

[MODIFY] ai_prompt_builder.py

Add prompt constraints enforcing that the Security Copilot is advisory-only and cannot mutate/create/activate/mitigate/close exposures, or modify validation results.

API Gateway

[NEW] exposures.py

Expose REST API endpoints:

GET /api/v1/exposures

GET /api/v1/exposures/open

GET /api/v1/exposures/critical

GET /api/v1/exposures/{id}

GET /api/v1/exposures/drift

GET /api/v1/exposures/summary

POST /api/v1/exposures

POST /api/v1/exposures/{id}/validate

POST /api/v1/exposures/{id}/accept

POST /api/v1/exposures/{id}/mitigate

POST /api/v1/exposures/{id}/close

Enforce standard role-based access checks and scope-level owner validations wrapped in StandardResponse.

[MODIFY] main.py

Register the /api/v1/exposures router.

Verification Plan

Automated Tests

Run pytest backend/tests/integration/test_exposures.py to execute a minimum of 60 integration tests, including:

test_exposure_auto_creation()

test_exposure_fingerprint_stability()

test_exposure_sync_preserves_identity()

test_exposure_validate_transition()

test_exposure_accept_transition()

test_exposure_mitigate_transition()

test_exposure_close_transition()

test_exposure_terminal_state_enforcement()

test_exposure_history_preserved()

test_attack_surface_inventory()

test_attack_surface_mapping()

test_exposure_correlation_findings()

test_exposure_correlation_risks()

test_exposure_correlation_alerts()

test_exposure_correlation_incidents()

test_exposure_correlation_cases()

test_exposure_correlation_hunts()

test_exposure_correlation_purple_team()

test_exposure_priority_calculation()

test_exposure_risk_score_calculation()

test_exposure_drift_detection()

test_snapshot_rebuild_consistency()

test_snapshot_rebuild_after_cache_deletion()

test_snapshot_rebuild_after_corruption()

test_ai_context_exposure_injection()

test_ai_advisory_only_enforcement()

test_rbac_scope_validation()

test_identity_preserved_after_mitigation()

test_identity_preserved_after_closure()

test_exposure_correlation_preservation()

test_attack_surface_category_registry()

Verification of registries, duplicates prevention, Celery integrations, and coverage metrics.

Execute full test suite pytest to ensure zero regressions across Sprints 1–23.