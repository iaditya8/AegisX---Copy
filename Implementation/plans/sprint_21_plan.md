# Sprint 21 — Implementation Plan

> **Paste your implementation plan for Sprint 21 below this line.**
> Delete this placeholder text when adding your content.

# Sprint 21: Threat Hunting Intelligence

Transform AegisX from a Threat Intelligence Platform into a Threat Hunting Intelligence Platform by introducing Hunt Management, Hunt Hypotheses, ATT&CK-driven Hunting, IOC-driven Hunting, Hunt Findings, Hunt Coverage Analytics, Hunt Drift Detection, and Hunt Intelligence Snapshots.

## User Review Required

> [!IMPORTANT]
> Please review the architecture and confirm that no external hunting integrations (e.g., Microsoft Defender Advanced Hunting, Splunk ES Hunting APIs) are to be integrated at this stage. Also, verify that the 45+ specified integration tests cover all your compliance scenarios.

## Open Questions

> [!WARNING]
> No specific open questions at this point as the requirements are precisely laid out and follow the patterns established in Sprints 13–20. Please approve if the plan looks correct.

## Proposed Changes

---

### Architectural Rules & Hardening

**Threat Hunt Source Rule:**
Sprint 21 must remain fully registry-driven and offline-capable. Threat Hunts may only leverage intelligence already present inside AegisX (Assets, Findings, Alerts, Incidents, Cases, Detections, ATT&CK Techniques, IOCs, Actors, Campaigns). No external connectivity, database migrations, or external hunting feeds are permitted.

**Hunt Identity Preservation Rule:**
If synchronization generates the same hunt fingerprint: preserve `hunt_id`, ownership, hypotheses, findings, history, timestamps, and escalation history. Do not create duplicate hunts. A new hunt may only be created when the hunt fingerprint changes, hunt type changes, hunt title changes, or related entities change.

---

### Domain Models

#### [NEW] [hunt.py](file:///c:/Users/Aditya/AegisX/backend/src/domain/entities/hunt.py)
- Create `HuntSeverity` enum (LOW, MEDIUM, HIGH, CRITICAL)
- Create `HuntStatus` enum (OPEN, ACTIVE, UNDER_REVIEW, ESCALATED, COMPLETED, CLOSED)
- Create `HuntType` enum (IOC_DRIVEN, ATTACK_DRIVEN, DETECTION_GAP, THREAT_ACTOR_DRIVEN, CAMPAIGN_DRIVEN, MANUAL)
- Create Pydantic response schemas: `HuntResponse`, `HuntHypothesisResponse`, `HuntFindingResponse`, and `HuntHistoryEntry`.

---

### Registries

#### [NEW] [hunt_type_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_type_registry.py)
- Maintain hunt type validation and configurations.

#### [NEW] [hunt_severity_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_severity_registry.py)
- Standardize hunt severity resolution logic.

---

### Core Services

#### [NEW] [hunt_fingerprint_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_fingerprint_service.py)
- Generate `SHA256(hunt_type, normalized_title, sorted_related_entities)` fingerprint.
- Enforce the **Hunt Fingerprint Stability Rule** (changes ONLY when hunt_type, title, or related entities change).

#### [NEW] [hunt_history_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_history_service.py)
- Maintain immutable append-only history tracking transitions (CREATED, ACTIVATED, etc.).
- Enforce the **Hunt History Preservation Rule** (never delete or modify).

#### [NEW] [hunt_hypothesis_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_hypothesis_service.py)
- Create, validate, and retrieve hunt hypotheses (e.g., "Hunt for APT29 infrastructure").

#### [NEW] [hunt_finding_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_finding_service.py)
- Track hunt findings and correlate them against existing entities (Assets, Findings, Alerts, Incidents, Cases, Detections, IOCs).

#### [NEW] [hunt_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_service.py)
- Manage hunt creation, synchronization, lifecycle management, and ownership assignment.
- Enforce the **Hunt State Machine** and the **Hunt Terminal State Rule** (CLOSED is terminal).

#### [NEW] [ioc_hunt_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ioc_hunt_service.py)
- Automatically generate hunts from IOC correlations, drift events, and reputation changes.

#### [NEW] [attack_hunt_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/attack_hunt_service.py)
- Automatically generate hunts from uncovered ATT&CK techniques, partially covered techniques, and detection gaps.

#### [NEW] [hunt_coverage_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_coverage_service.py)
- Compute attack_coverage, ioc_coverage, campaign_coverage, and actor_coverage.

#### [NEW] [hunt_drift_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_drift_service.py)
- Detect hunt lifecycle changes and coverage changes, and emit `hunt.drift` and `hunt.coverage_changed` workflow events.

#### [NEW] [hunt_snapshot_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/hunt_snapshot_service.py)
- Rebuildable cache for total_hunts, open_hunts, active_hunts, attack_coverage, ioc_coverage, etc.
- Enforce the **Hunt Snapshot Consistency Rule**.

---

### Integrations

#### [MODIFY] [worker.py](file:///c:/Users/Aditya/AegisX/backend/src/infrastructure/celery/worker.py)
- After Threat Intelligence processing, safely invoke `HuntService.sync_hunts()`, `IOCHuntService.sync_ioc_hunts()`, `AttackHuntService.sync_attack_hunts()`, `HuntCoverageService.calculate()`, `HuntDriftService.process_drift()`, and `HuntSnapshotService.generate_snapshot()`.

#### [MODIFY] [ai_context_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_context_builder.py)
- Inject hunt_summary, hunt_status, hypotheses, findings, and coverage block into asset, finding, incident, case, and executive AI context profiles.

#### [MODIFY] [ai_prompt_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_prompt_builder.py)
- Add constraints that AI Security Copilot cannot create, activate, modify, assign, complete, or close hunts, hypotheses, or findings (Advisor-only).

---

### API Gateway

#### [NEW] [hunts.py](file:///c:/Users/Aditya/AegisX/backend/src/api/v1/routers/hunts.py)
- Expose REST endpoints (GET list, GET id, GET states, GET metrics, POST activate/review/complete/close/escalate).
- Enforce standard RBAC and Scope filtering rules.

#### [MODIFY] [main.py](file:///c:/Users/Aditya/AegisX/backend/src/main.py)
- Register the new `hunts` router.

---

## Verification Plan

### Automated Tests
- Run `pytest backend/tests/integration/test_hunts.py` to execute a minimum of 45 integration tests covering:
  - test_hunt_auto_creation()
  - test_hunt_fingerprint_stability()
  - test_hunt_sync_preserves_identity()
  - test_hunt_sync_preserves_hypotheses()
  - test_hunt_sync_preserves_findings()
  - test_hunt_activate_transition(), test_hunt_review_transition(), test_hunt_complete_transition(), test_hunt_close_transition()
  - test_hunt_terminal_state_enforcement()
  - test_hunt_history_preserved()
  - test_hypothesis_creation(), test_hypothesis_preservation()
  - test_hunt_findings_creation(), test_hunt_findings_preservation()
  - test_ioc_hunt_generation(), test_ioc_reputation_hunt_generation()
  - test_attack_hunt_generation(), test_detection_gap_hunt_generation()
  - test_hunt_coverage_calculation(), test_hunt_coverage_regression_detection()
  - test_hunt_drift_detection()
  - test_snapshot_rebuild_consistency()
  - test_hunt_identity_preserved_after_escalation(), test_hunt_identity_preserved_after_completion()
  - test_ai_context_hunt_injection()
  - test_rbac_hunt_scope_validation()
  - And all other requested tests to ensure >85% code coverage.
- Run `pytest` to ensure 0 regressions.

### Manual Verification
- Review API responses to confirm RBAC enforcement and compatibility.
