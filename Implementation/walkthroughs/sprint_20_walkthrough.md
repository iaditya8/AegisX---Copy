# Sprint 20 — Walkthrough

> **Paste your walkthrough for Sprint 20 below this line.**
> Delete this placeholder text when adding your content.

# Walkthrough: Sprint 20 – Threat Intelligence & IOC Intelligence

Transform AegisX from a Detection Engineering Intelligence Platform into a Threat Intelligence & IOC Intelligence Platform by introducing IOC management, threat actors, campaigns, correlation engine, drift detection, snapshot caches, and AI context integrations.

## Changes Completed

### Domain Models & Registries
- [NEW] [threat_intelligence.py](file:///c:/Users/Aditya/AegisX/backend/src/domain/entities/threat_intelligence.py): Implements core domain structures `IOCType`, `IOCSeverity`, `IOCStatus`, `ThreatFeedType`, `IOCResponse`, `ThreatActorResponse`, `CampaignResponse`, and `IOCCorrelationResponse`.
- [NEW] [ioc_type_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ioc_type_registry.py): Provides type-based regex validation and normalization for domain values.
- [NEW] [threat_feed_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/threat_feed_registry.py): Pre-seeds system threat feeds (INTERNAL, COMMUNITY, COMMERCIAL).
- [NEW] [threat_actor_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/threat_actor_registry.py): Pre-seeds actor entries with stable deterministic UUIDs for `APT29`, `APT28`, `Lazarus`, and `FIN7`.
- [NEW] [campaign_registry.py](file:///c:/Users/Aditya/AegisX/backend/src/services/campaign_registry.py): Maps actor attributions to campaigns with deterministic IDs.

### Core Services
- [NEW] [ioc_fingerprint_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ioc_fingerprint_service.py): Computes stable fingerprints via `SHA256(ioc_type, normalized_ioc_value)`.
- [NEW] [ioc_history_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ioc_history_service.py): Implements immutable append-only historical audit trails.
- [NEW] [ioc_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ioc_service.py): Orchestrates the IOC lifecycle including creation, sync, expiration, and revocation while enforcing terminal state restrictions.
- [NEW] [threat_actor_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/threat_actor_service.py) & [campaign_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/campaign_service.py): Manages lookup attribution and campaign relationships dynamically mapped from registries and active IOCs.
- [NEW] [ioc_correlation_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ioc_correlation_service.py): Links active IOCs to Assets, Findings, Alerts, Incidents, Cases, and Detections while maintaining historical correlation identities.
- [NEW] [ioc_drift_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ioc_drift_service.py): Emits workflow events (`ioc.drift`, `ioc.reputation_changed`) for status, reputation, campaign, or actor modifications.
- [NEW] [threat_intelligence_snapshot_service.py](file:///c:/Users/Aditya/AegisX/backend/src/services/threat_intelligence_snapshot_service.py): Cache-only, rebuildable threat intelligence metrics snapshot dashboard.

### Integrations
- [MODIFY] [worker.py](file:///c:/Users/Aditya/AegisX/backend/src/infrastructure/celery/worker.py): Injects correlation, drift detection, and snapshot generation processes inside step processing.
- [MODIFY] [ai_context_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_context_builder.py): Injects threat intelligence block (matches, actors, campaigns, reputations, correlations, summaries) into all context profiles.
- [MODIFY] [ai_prompt_builder.py](file:///c:/Users/Aditya/AegisX/backend/src/services/ai_prompt_builder.py): Restricts AI from performing mutations on threat intelligence properties.

### API Gateway
- [NEW] [threat_intelligence.py](file:///c:/Users/Aditya/AegisX/backend/src/api/v1/routers/threat_intelligence.py): Exposes versioned endpoints with standard response shapes and role-based access controls (RBAC).
- [MODIFY] [main.py](file:///c:/Users/Aditya/AegisX/backend/src/main.py): Registers the threat intelligence router prefix.

---

## Validation & Testing Results

### Automated Tests
Successfully ran the threat intelligence integration test suite using:
`.venv\Scripts\pytest backend/tests/integration/test_threat_intelligence.py`

Result:
```
============================= 38 passed in 0.19s ==============================
```

Successfully executed the complete regression suite to confirm zero regressions across all modules:
`.venv\Scripts\pytest`

Result:
```
====================== 421 passed, 10 warnings in 12.07s ======================
```

### Verification Checks

| Requirement / Rule | Verification Status | Details |
| --- | --- | --- |
| **Threat Intelligence Source Rule** | ✅ Confirmed | All threat feeds, actors, and campaigns are registry-driven; no external HTTP connections are made. |
| **Fingerprint Stability Rule** | ✅ Confirmed | Fingerprints are generated deterministically based purely on `ioc_type` and `normalized_ioc_value`. |
| **IOC Terminal State Rule** | ✅ Confirmed | `EXPIRED` and `REVOKED` IOCs are terminal and cannot be transitioned back to active. |
| **IOC History Preservation Rule** | ✅ Confirmed | Immutable history appends new events without changing, reordering, or deleting existing entries. |
| **IOC Correlation Identity Preservation** | ✅ Confirmed | Same target entity references preserve their `correlation_id` and `created_at` timestamp. |
| **Snapshot Rebuild Consistency** | ✅ Confirmed | Snapshot caches are generated dynamically from active records when invalidated. |
| **AI Advisor Enforcement** | ✅ Confirmed | Prompt builder constraints strictly prohibit the AI from creating/mutating IOC elements. |
| **RBAC validation** | ✅ Confirmed | Endpoints validate scope ownership and role-based permissions (`admin`, `operator`, `reader`). |

---

## Backward Compatibility Statement
All Sprint 20 endpoints, models, and background task hooks maintain backward compatibility with Sprints 1–19. The database schema has not been modified (zero DB migrations required).

- [x] Create domain models: `threat_intelligence.py`
- [x] Create registries:
  - [x] `ioc_type_registry.py`
  - [x] `threat_feed_registry.py`
  - [x] `threat_actor_registry.py`
  - [x] `campaign_registry.py`
- [x] Create core services:
  - [x] `ioc_fingerprint_service.py`
  - [x] `ioc_history_service.py`
  - [x] `ioc_service.py`
  - [x] `threat_actor_service.py`
  - [x] `campaign_service.py`
  - [x] `ioc_correlation_service.py`
  - [x] `ioc_drift_service.py`
  - [x] `threat_intelligence_snapshot_service.py`
- [x] Modify `worker.py`
- [x] Modify AI integration:
  - [x] `ai_context_builder.py`
  - [x] `ai_prompt_builder.py`
- [x] Create API router:
  - [x] `api/v1/routers/threat_intelligence.py`
  - [x] Register router in `main.py`
- [x] Create integration tests: `backend/tests/integration/test_threat_intelligence.py`
