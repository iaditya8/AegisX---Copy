# Sprint 30 — Walkthrough

> **Paste your walkthrough for Sprint 30 below this line.**
> Delete this placeholder text when adding your content.

Sprint 30 — Cyber Risk Quantification Intelligence — Walkthrough

Overview

Sprint 30 transitions AegisX into a Cyber Risk Quantification Intelligence Platform. This release introduces registries (Scenario, Frequency, Impact), deterministic risk evaluations, risk forecasting, trend tracking, baseline drift, and Celery integrations.

Files Created & Modified in Sprint 30

1. Domain Model

cyber_risk_quantification.py [NEW] — Defines enums (RiskSeverity, RiskQuantificationStatus, RiskScenarioType) and response schemas (CyberRiskResponse, RiskScenarioResponse, RiskForecastResponse, RiskHistoryEntry).

2. Registries

risk_scenario_registry.py [NEW] — Registers pre-seeded risk scenarios (DATA_BREACH, RANSOMWARE, INSIDER_THREAT, etc.).

risk_frequency_registry.py [NEW] — Registers risk occurrence frequencies (RARE, OCCASIONAL, LIKELY, FREQUENT) with ARO mappings.

risk_impact_registry.py [NEW] — Registers loss impact ratios.

3. Core Services

Service

Purpose / Implementation Details

risk_quantification_fingerprint_service.py [NEW]

Computes stable SHA-256 fingerprints based on scenario type, scope ID, and title.

risk_history_service.py [MODIFY]

Implements immutable, append-only history event logging.

loss_expectancy_service.py [NEW]

Calculates deterministic Single Loss Expectancy (SLE) and Annual Loss Expectancy (ALE).

residual_risk_service.py [NEW]

Calculates residual risk and mitigation effectiveness.

risk_forecast_service.py [NEW]

Generates deterministic risk projections.

risk_trend_service.py [NEW]

Computes trends of ALE over time.

risk_drift_service.py [MODIFY]

Detects risk level fluctuations (increase, decrease, critical crossing) and merges asset risk drift from Sprints 1-29.

risk_quantification_snapshot_service.py [NEW]

In-memory, cache-only, rebuildable snapshots of risk metrics.

cyber_risk_quantification_service.py [NEW]

Manages the risk lifecycle (ACTIVE -> IN_MITIGATION -> MITIGATED -> CLOSED) and identity preservation.

4. Integrations

worker.py [MODIFY] — Runs periodic risk synchronization and calculations in a crash-safe task block.

ai_context_builder.py [MODIFY] — Injects risk metrics and trends into AI context.

ai_prompt_builder.py [MODIFY] — Appends prompt instructions blocking risk mutations by AI.

main.py [MODIFY] — Registers API router /api/v1/cyber-risk-quantification.

cyber_risk_quantification.py [NEW] — Router exposing endpoint routes with scope-based RBAC enforcement.

Architectural Constraints & Hardening Rules

1. Cyber Risk Terminal State Rule

CLOSED is a terminal state. Once set, synchronization, worker refreshes, forecasting, drift processing, and snapshots cannot transition a risk back to an active state.

2. Risk History Preservation Rule

History entries are immutable and append-only. Only new events are appended, preventing any mutation, deletion, or reordering of historical records.

3. Risk Calculation Determinism Rule

SLE, ALE, residual risk, and mitigation effectiveness calculations must be deterministic. Identical inputs must always produce identical outputs.

Calculations are strictly read-only and must never mutate risk records, history, forecasts, or snapshots.

4. Risk Forecast Preservation Rule

Forecasts are derived, read-only intelligence and must never mutate risk records or history. Forecast generation must be deterministic and reproducible.

5. Quantified Risk Snapshot Consistency Rule

Snapshots are cache-only, non-authoritative, and rebuildable. Missing or corrupted snapshots trigger a transparent rebuild from active source data.

Test Results

117/117 integration tests passed in test_cyber_risk_quantification.py.
