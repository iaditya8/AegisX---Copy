# Sprint 20 — Implementation Plan

> **Paste your implementation plan for Sprint 20 below this line.**
> Delete this placeholder text when adding your content.

# Sprint 20: Threat Intelligence & IOC Intelligence

Transform AegisX from a Detection Engineering Intelligence Platform into a Threat Intelligence & IOC Intelligence Platform by introducing IOC management, correlation, threat actor tracking, and drift detection.

## User Review Required

> [!IMPORTANT]
> Please review the architecture and confirm that no external threat feed APIs are to be integrated at this stage (registry-driven only). Also verify that the 35+ specified integration tests cover all your compliance scenarios.

## Open Questions

> [!WARNING]
> No specific open questions at this point as the requirements are extremely precise. Please approve if the plan looks correct.

## Proposed Changes

---

### Architectural Rules & Hardening

**Threat Intelligence Source Rule:**
Sprint 20 operates exclusively using in-memory registries. No external integrations (e.g., MISP, OpenCTI, VirusTotal, AbuseIPDB, AlienVault OTX, Recorded Future, CrowdStrike Intelligence, Microsoft TI) are permitted. Sprint 20 remains deterministic, offline-capable, and registry-driven.

---

### Domain Models

#### [NEW] [threat_intelligence.py](file:///c:/Users/Aditya/AegisX/backend/src/domain/entities/threat_intelligence.py)
- Create `IOCType` enum (IP_ADDRESS, DOMAIN, URL, EMAIL, MD5, SHA1, SHA256)
- Create `IOCSeverity` enum (LOW, MEDIUM, HIGH, CRITICAL)
- Create `IOCStatus` enum (ACTIVE, EXPIRED, REVOKED)
- Create `ThreatFeedType` enum (INTERNAL, COMMUNITY, COMMERCIAL)
- Create `IOCResponse`, `ThreatActorResponse`, and `CampaignResponse` Pydantic models.

---

### Registries

#### [NEW] [ioc_type_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ioc_type_registry.py)
- Maintain IOC type validation.

#### [NEW] [threat_feed_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/threat_feed_registry.py)
- Pre-seed feeds: INTERNAL, COMMUNITY, COMMERCIAL.

#### [NEW] [threat_actor_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/threat_actor_registry.py)
- Pre-seed actors: APT29, APT28, Lazarus, FIN7.

#### [NEW] [campaign_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/campaign_registry.py)
- Provide sample campaign mappings.

---

### Core Services

#### [NEW] [ioc_fingerprint_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ioc_fingerprint_service.py)
- Generate SHA256(ioc_type, normalized_ioc_value) fingerprint. Enforce Fingerprint Stability Rule.

#### [NEW] [ioc_history_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ioc_history_service.py)
- Append-only immutable history tracking transitions and updates.
- **IOC History Preservation Rule**: IOC history entries are immutable. Existing history entries must never be modified, rewritten, reordered, or deleted. Expiration, revocation, synchronization, reputation changes, actor attribution changes, campaign attribution changes, and drift events must append new records. IOC history must survive synchronization runs, terminal state transitions, snapshot rebuilds, and drift processing. History is the authoritative audit trail and must never be reconstructed from IOC state.

#### [NEW] [ioc_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ioc_service.py)
- Manage IOC creation, synchronization, expiration, and revocation. Enforce Terminal State Rule for EXPIRED/REVOKED.

#### [NEW] [threat_actor_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/threat_actor_service.py)
- Manage actor intelligence, attribution, and relationships.

#### [NEW] [campaign_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/campaign_service.py)
- Manage campaign attribution and IOC relationships.

#### [NEW] [ioc_correlation_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ioc_correlation_service.py)
- Correlate IOCs against Assets, Findings, Alerts, Incidents, Cases, Detections.
- **IOC Correlation Identity Preservation Rule**: If correlation processing is rerun and produces the same IOC fingerprint and target entity reference: preserve correlation_id, timestamps, and history. Do not create duplicate correlations. A new correlation may only be created if the IOC fingerprint changes OR the target entity changes.

#### [NEW] [ioc_drift_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ioc_drift_service.py)
- Detect changes and emit workflow events (e.g., `ioc.drift`, `ioc.reputation_changed`).

#### [NEW] [threat_intelligence_snapshot_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/threat_intelligence_snapshot_service.py)
- Cache-only, rebuildable snapshots for threat intel metrics and fast retrieval.

---

### Integrations

#### [MODIFY] [worker.py](file:///c:/Users/Aditya/AegisX/backend/src/worker.py)
- Add IOCService.sync_iocs(), IOCDriftService.process_drift(), and ThreatIntelligenceSnapshotService.generate_snapshot() after Detection Engineering processing.

#### [MODIFY] [ai_context_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_context_builder.py)
- Inject IOC and threat intelligence context into all AI context profiles.

#### [MODIFY] [ai_prompt_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_prompt_builder.py)
- Add constraint: AI Security Copilot cannot create, modify, revoke IOCs, campaigns, actors, or correlations.

---

### API Gateway

#### [NEW] [threat_intelligence.py](file:///c:/Users/Aditya/AegisX/backend/src/api/v1/routers/threat_intelligence.py)
- Implement endpoints:
  - GET `/api/v1/threat-intelligence/iocs`
  - GET `/api/v1/threat-intelligence/iocs/{id}`
  - GET `/api/v1/threat-intelligence/actors`
  - GET `/api/v1/threat-intelligence/campaigns`
  - GET `/api/v1/threat-intelligence/correlations`
  - GET `/api/v1/threat-intelligence/summary`
  - POST `/api/v1/threat-intelligence/iocs`
  - POST `/api/v1/threat-intelligence/iocs/{id}/expire`
  - POST `/api/v1/threat-intelligence/iocs/{id}/revoke`

#### [MODIFY] [main.py](file:///c:/Users/Aditya/AegisX/backend/src/main.py)
- Register the new `threat_intelligence` router.

---

## Verification Plan

### Automated Tests
- Run `pytest backend/tests/integration/test_threat_intelligence.py` to execute a minimum of 41 integration tests covering all requirements, including the following specific scenarios:
  - test_ioc_auto_creation()
  - test_ioc_fingerprint_stability()
  - test_ioc_sync_preserves_identity()
  - test_ioc_expire_transition()
  - test_ioc_revoke_transition()
  - test_ioc_terminal_state_enforcement()
  - test_ioc_history_preserved()
  - test_threat_actor_lookup()
  - test_campaign_lookup()
  - test_ioc_correlation_assets()
  - test_ioc_correlation_findings()
  - test_ioc_correlation_alerts()
  - test_ioc_correlation_incidents()
  - test_ioc_correlation_cases()
  - test_ioc_correlation_detections()
  - test_ioc_correlation_preservation()
  - test_ioc_reputation_change_detection()
  - test_ioc_drift_detection()
  - test_snapshot_rebuild_consistency()
  - test_ioc_identity_preserved_after_expiration()
  - test_ioc_identity_preserved_after_revocation()
  - test_ai_context_threat_intelligence_injection()
  - test_rbac_threat_intelligence_scope_validation()
  - **[NEW]** test_ioc_duplicate_prevention()
  - **[NEW]** test_ioc_correlation_identity_preserved()
  - **[NEW]** test_ioc_snapshot_rebuild_after_cache_deletion()
  - **[NEW]** test_ioc_terminal_state_not_reactivated_by_sync()
  - **[NEW]** test_campaign_relationship_preservation()
  - **[NEW]** test_actor_relationship_preservation()
- Run `pytest` to ensure 0 regressions.

### Manual Verification
- Review API responses to confirm RBAC enforcement and standard response formatting.
