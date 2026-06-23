# Sprint 12 — Implementation Plan

> **Paste your implementation plan for Sprint 12 below this line.**
> Delete this placeholder text when adding your content

# Sprint 12 Implementation Plan: Exposure Decision Support Platform

Transform AegisX from an Exposure Intelligence Platform into an Exposure Decision Support Platform. The platform will guide analysts on what to fix, investigate, and review deterministically, backed by explainable priority factors and rules.

## User Review Required

> [!IMPORTANT]
> The AI Copilot is strictly advisory and will only consume the deterministic outputs of the newly created Recommendation and Prioritization services. It will not generate arbitrary actions.

> [!CAUTION]
> Recommendation tracking and history will be maintained strictly in-memory. Database migration for persistent state tracking is out of scope for this Sprint, in accordance with the requirement.

## Cross-Sprint Compatibility Requirement

> [!IMPORTANT]
> **Mandatory Review:** Before implementation, all previously implemented sprints must be reviewed. The implementation must validate compatibility with:
> - Sprint 7 Asset Intelligence
> - Sprint 8 Vulnerability Intelligence
> - Sprint 9 Correlation & Risk Intelligence
> - Sprint 10 Reporting & Analytics
> - Sprint 11 AI Security Copilot
> 
> The implementation must:
> - Reuse existing services.
> - Reuse existing snapshots.
> - Reuse existing APIs.
> - Reuse existing workflow events.
> - Reuse existing audit/history mechanisms.
> 
> Do not introduce duplicate intelligence models. Do not replace existing architecture. Extend existing architecture only.
> At completion, execute full regression validation against all previous sprint test suites (all 182+ tests). This requirement will persist in all future sprints.

## Open Questions

- Should we include any specific threshold limits for "high_risk_asset" in the Priority Factor Registry, or follow existing critical thresholds? (Plan: I will default to `risk_score >= 80` for high risk).
- Should the `recommendation.created` events be published to the existing `workflow_events` table as part of the scan lifecycle? (Plan: Yes, matching previous event integration).

## Proposed Changes

---

### Core Domain Models

#### [NEW] [recommendation.py](file:///C:/Users/Aditya/AegisX/backend/src/domain/entities/recommendation.py)
Defines the Pydantic schemas for the decision support output:
- Enum: `RecommendationType` (PATCH, INVESTIGATE, HARDEN, REVIEW, MONITOR, VALIDATE)
- Enum: `RecommendationPriority` (LOW, MEDIUM, HIGH, CRITICAL)
- `RecommendationResponse` (incorporates the **Explanation Model** to remain deterministic and auditable):
  ```json
  {
    "recommendation_id": "...",
    "priority": "CRITICAL",
    "type": "PATCH",
    "asset_id": "...",
    "finding_id": "...",
    "title": "Patch internet-facing critical vulnerability",
    "reason": "Critical finding exists on an external asset",
    "risk_score": 87,
    "supporting_factors": [
        {
            "factor": "critical_finding_present",
            "impact": 25
        },
        {
            "factor": "internet_exposed",
            "impact": 20
        }
    ]
  }
  ```
- `PriorityRankingResponse` (normalized score 0-100, rank, entity info)
- `InvestigationGuidanceResponse` (list of investigation steps for a finding)
- `RecommendationSnapshotResponse` (aggregated totals for an asset)

---

### Prioritization Engine

#### [NEW] [priority_factor_registry.py](file:///C:/Users/Aditya/AegisX/backend/src/services/priority_factor_registry.py)
Centralizes the base weights for ranking:
- Maps factors like `critical_finding` (30), `high_risk_asset` (25), `internet_exposed` (20), `rediscovered_finding` (15), `high_criticality` (10) to deterministic point values.

#### [NEW] [prioritization_service.py](file:///C:/Users/Aditya/AegisX/backend/src/services/prioritization_service.py)
Ranks assets, findings, technologies, and products:
- Applies `PriorityFactorRegistry` base weights.
- Normalizes priority scores into a 0-100 scale. No arbitrary scales.
- Implements `get_top_assets(limit=10)`, `get_top_findings(limit=20)`, `get_top_technologies(limit=20)`, `get_top_products(limit=20)`.

---

### Recommendation Engine

#### [NEW] [recommendation_rules_registry.py](file:///C:/Users/Aditya/AegisX/backend/src/services/recommendation_rules_registry.py)
Centralizes recommendation classification rules:
- Maps states (e.g., `external_critical_finding`, `high_risk_asset`, `rediscovered_finding`) to deterministic Priorities and Action Types.

#### [NEW] [recommendation_fingerprint_service.py](file:///C:/Users/Aditya/AegisX/backend/src/services/recommendation_fingerprint_service.py)
Recommendation Identity & Deduplication:
- Generates stable recommendation fingerprints using `SHA256(asset_id, finding_id, recommendation_type, recommendation_title)`.
- **Fingerprint Stability Requirements:**
  - The fingerprint must remain stable across: rescans, recommendation recomputation, recommendation priority changes, and recommendation aging updates.
  - The fingerprint must change only when: asset_id changes, finding_id changes, recommendation_type changes, or recommendation_title changes.
  - This prevents accidental fingerprint churn that would break aging and history.
- **Requirements:**
  - Prevent duplicate recommendations.
  - Recompute existing recommendations instead of creating duplicates.
  - Preserve recommendation history across recalculations.
  - Recommendation aging must continue across recomputations.
  - Recommendation priority changes must generate:
    - `recommendation.priority_changed` event
    - audit log entries
    - history entries

#### [NEW] [recommendation_service.py](file:///C:/Users/Aditya/AegisX/backend/src/services/recommendation_service.py)
Generates actionable recommendations:
- Consumes findings, risk scores, criticality, and exposure.
- Evaluates contexts against `RecommendationRulesRegistry`.
- Outputs deterministic `RecommendationResponse` instances.
- Generates Technology & Product specific recommendations for future enterprise reporting.

---

### Investigation and History Services

#### [NEW] [investigation_assistance_service.py](file:///C:/Users/Aditya/AegisX/backend/src/services/investigation_assistance_service.py)
Generates actionable, deterministic analyst guidance arrays based on the finding template and context without executing remediation. Guidance generated for critical findings, high findings, rediscovered findings, external assets, and high-risk assets.

#### [NEW] [recommendation_snapshot_service.py](file:///C:/Users/Aditya/AegisX/backend/src/services/recommendation_snapshot_service.py)
In-memory caching of recommendation totals per asset.
- Implements `generate_snapshot(asset_id)`, `update_snapshot(asset_id)`, `get_snapshot(asset_id)`.

#### [NEW] [recommendation_history_service.py](file:///C:/Users/Aditya/AegisX/backend/src/services/recommendation_history_service.py)
Tracks recommendation lifecycle events and **Recommendation Aging** in-memory:
- Tracks: `created_at`, `last_seen`, `times_recomputed`.
- Provides: `get_recommendation_age_days()` and `get_stale_recommendations(days=30)`.
- Records events like `recommendation.created`, `recommendation.priority_changed`, and `recommendation.closed`.

---

### Integration Layers

#### [NEW] [recommendations.py](file:///C:/Users/Aditya/AegisX/backend/src/api/v1/routers/recommendations.py)
Exposes read-only API endpoints enforcing RBAC (admin, operator) and scope ownership checks:
- `GET /api/v1/recommendations/assets/{id}`
- `GET /api/v1/recommendations/findings/{id}`
- `GET /api/v1/recommendations/assets/{id}/guidance`
- `GET /api/v1/recommendations/top-assets`
- `GET /api/v1/recommendations/top-findings`
- `GET /api/v1/recommendations/top-technologies`
- `GET /api/v1/recommendations/top-products`

#### [MODIFY] [worker.py & Existing Services] - Event-Driven Updates
- **`worker.py`**: Automatically triggers `RecommendationSnapshotService.update_snapshot(asset_id)` upon completion of scans.
- **Event-Driven Hooks**: The Snapshot must also refresh automatically whenever state changes. Hooks will be added to:
  - `FindingService` (when findings change)
  - `AssetRiskSnapshotService` (when risk score or criticality changes)
  - `CorrelationSnapshotService` (when exposure state changes)

#### [MODIFY] [copilot_services]
Modifies `asset_copilot_service.py`, `finding_copilot_service.py`, `executive_copilot_service.py`:
- Injects deterministic outputs from the new engines into the LLM context generation process.
- Modifies AI prompts to act strictly as explanations of these recommendations, actively restricting the LLM from hallucinating custom actions or generating overriding priorities.

---

## Verification Plan

### Automated Tests
- Create `backend/tests/integration/test_recommendations.py` to cover:
  - Generation and prioritization assignment
  - **`test_recommendation_deduplication`**: Verify that repeated scans do not create duplicate recommendations for the same asset/finding context.
  - **`test_recommendation_priority_change`**: Verify that recommendation priority changes generate the `recommendation.priority_changed` event, history record, and audit log entry.
  - **`test_recommendation_aging_preserved_after_recompute`**: Verify `created_at` remains unchanged, `last_seen` updates, `times_recomputed` increments, and recommendation fingerprint remains unchanged after recommendation recomputation.
  - Priority algorithm normalization (0-100)
  - Guidance generation logic
  - History tracking (aging, recomputation) and cache snapshotting behavior
  - Integration of recommendation contexts into AI prompt execution
  - RBAC controls on endpoints
- **Cross-Sprint Regression:** Execute the full test suite (`.venv\Scripts\pytest`) to guarantee backwards compatibility.
- Validate compliance via formatting checks (`ruff check backend/` and `black backend/`).

