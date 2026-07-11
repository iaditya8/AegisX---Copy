# Phase 2 Sprint 01: Unified Correlation Engine Blueprint

This document details the architectural design for the AegisX **Unified Correlation Engine** to be implemented in Phase 2 Sprint 01. The design reuses the existing database repositories, transactional `UnitOfWork` lifecycle, Security Graph path traversals, Intelligence Fabric propagation weights, and outbox event streams.

> **Revision Note**: This blueprint incorporates six Chief Architect modifications applied after the initial design review: Correlation History audit trail, cluster fingerprinting, polymorphic signal relationship table, event consumer service, score explainability breakdown, rule execution provenance (`CorrelationRuleMatch`), and rule versioning for historically reproducible provenance.

---

## 1. Services Required

To enable correlation processing without coupling, **four** new services are introduced:

### A. `CorrelationRuleEngine` (`correlation_rule_engine.py`)
- **Purpose**: Evaluates active correlation rules against incoming signals (findings, alerts, IOCs).
- **Core Operations**:
  - Matches rule conditions (e.g. mapping vulnerability CVEs to IOC indicators).
  - Triggers topological graph queries to determine target proximity.
  - Returns positive matches with aggregated threat details.

### B. `CorrelationAggregatorService` (`correlation_aggregator_service.py`)
- **Purpose**: Aggregates distinct signals belonging to the same root asset and calculates the unified priority score.
- **Core Operations**:
  - Joins findings, active hunts, and fabric weights.
  - Applies decay and weighting policies.
  - Outputs a consolidated `CorrelationClusterRecord` with a full `score_breakdown_json` for SOC explainability.

### C. `CorrelationIncidentBridge` (`correlation_incident_bridge.py`)
- **Purpose**: Automates incident creation and escalation based on correlation engine outcomes.
- **Core Operations**:
  - Packages correlated signals into a unified case evidence collection.
  - Calls `IncidentService.create_or_sync_incident` via the `UnitOfWork`.

### D. `CorrelationEventConsumer` (`correlation_event_consumer.py`) *(Architectural Addition)*
- **Purpose**: Decoupled orchestration layer that receives domain events and drives the full correlation pipeline.
- **Responsibilities**:
  1. Receive inbound event (e.g. `finding.created`, `alert.received`).
  2. Load full signal context from repositories.
  3. Invoke `CorrelationRuleEngine` to evaluate matching rules.
  4. Invoke `CorrelationAggregatorService` to update or create the cluster.
  5. Persist `CorrelationRuleMatch` record(s) for each matched rule within the same `UnitOfWork` transaction.
  6. Write `CorrelationHistory` record within the same `UnitOfWork` transaction.
  7. Emit outbound events via the outbox.
- **Rationale**: Separates event handling orchestration from correlation logic, keeping each service unit-testable in isolation.

---

## 2. Database Models Required

**Six** persistent database tables are required. The original two-table design has been expanded with four additional tables to support audit trails, polymorphic signal relationships, cluster fingerprinting, and rule execution provenance.

### A. `CorrelationRule` (`models.py`)
```python
class CorrelationRule(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "correlation_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="active")  # active, inactive
    condition_expression = Column(JSONB, nullable=False)  # JSON rule structure
    priority_level = Column(String(50), nullable=False)  # critical, high, medium, low
    rule_version = Column(Integer, nullable=False, default=1)  # incremented on each rule edit

    rule_matches = relationship("CorrelationRuleMatch", back_populates="rule", cascade="all, delete-orphan")
```

> **Rule Versioning**: `rule_version` is an integer incremented atomically every time a `CorrelationRule`'s `condition_expression` or `priority_level` is modified. The version is **never reset** — it only increases. This ensures that historical `CorrelationRuleMatch` records continue to reference the exact logical version of the rule that was active at evaluation time, even after the rule has since been edited.

### B. `CorrelationCluster` (`models.py`)
```python
class CorrelationCluster(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "correlation_clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    unified_score = Column(Float, default=0.0)
    score_breakdown_json = Column(JSONB, nullable=True)
    # e.g. {"asset": 4.5, "finding": 2.8, "fabric": 1.7, "risk_adjustment": -0.5}
    status = Column(String(50), default="open")  # open, triaged, closed
    fingerprint = Column(String(255), nullable=False)  # deterministic hash of root signals
    associated_incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True)

    # Signals accessed via CorrelationClusterSignal relationship table
    signals = relationship("CorrelationClusterSignal", back_populates="cluster", cascade="all, delete-orphan")
    history = relationship("CorrelationHistory", back_populates="cluster", cascade="all, delete-orphan")
    rule_matches = relationship("CorrelationRuleMatch", back_populates="cluster", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "fingerprint", name="uq_cluster_tenant_fingerprint"),
    )
```

> **Modification 2 — Cluster Fingerprinting**: The `fingerprint` column is a deterministic hash derived from the root asset ID and the sorted set of contributing signal identifiers. The `UniqueConstraint` on `(tenant_id, fingerprint)` guarantees that identical signal combinations never produce duplicate clusters. The `CorrelationAggregatorService` is responsible for computing this hash before upsert.

### C. `CorrelationClusterSignal` (`models.py`) *(Replaces ARRAY fields)*
```python
class CorrelationClusterSignal(Base, TenantOwnedMixin):
    __tablename__ = "correlation_cluster_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("correlation_clusters.id", ondelete="CASCADE"), nullable=False)
    signal_type = Column(String(100), nullable=False)
    # finding | alert | ioc | incident | hunt | decision | posture | program
    signal_id = Column(UUID(as_uuid=True), nullable=False)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    cluster = relationship("CorrelationCluster", back_populates="signals")

    __table_args__ = (
        UniqueConstraint("cluster_id", "signal_type", "signal_id", name="uq_cluster_signal"),
    )
```

> **Modification 3 — Polymorphic Signal Table**: `ARRAY(UUID)` fields have been removed from `CorrelationCluster`. The `signal_type` discriminator column allows the engine to correlate any current or future signal domain (Finding, Alert, IOC, Incident, Risk, Posture, Hunt, Program, Decision) without schema changes. Adding a new signal type requires only a new `signal_type` string value — no DDL migration.

### D. `CorrelationHistory` (`models.py`) *(New)*
```python
class CorrelationHistory(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "correlation_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("correlation_clusters.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(100), nullable=False)
    # cluster_created | score_increased | cluster_escalated | incident_created | cluster_resolved
    details_json = Column(JSONB, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    cluster = relationship("CorrelationCluster", back_populates="history")
```

> **Modification 1 — Correlation History**: Clusters are not static — they evolve as new signals arrive, scores increase, and incidents are escalated. `CorrelationHistory` provides a full immutable audit trail of every state transition. The `CorrelationEventConsumer` writes a history record inside the same `UnitOfWork` transaction as the cluster update, guaranteeing consistency. Supported `event_type` values: `cluster_created`, `score_increased`, `cluster_escalated`, `incident_created`, `cluster_resolved`.

### E. `CorrelationRuleMatch` (`models.py`) *(New)*
```python
class CorrelationRuleMatch(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "correlation_rule_matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("correlation_rules.id", ondelete="CASCADE"), nullable=False)
    rule_version_used = Column(Integer, nullable=False)  # snapshot of rule_version at match time
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("correlation_clusters.id", ondelete="CASCADE"), nullable=False)
    matched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confidence = Column(Float, nullable=False)  # 0.0 – 1.0
    evidence_json = Column(JSONB, nullable=True)
    # e.g. {"matched_signals": ["finding:uuid", "ioc:uuid"], "condition_hits": ["cve_match", "exposure_level"]}

    rule = relationship("CorrelationRule", back_populates="rule_matches")
    cluster = relationship("CorrelationCluster", back_populates="rule_matches")
```

> **CorrelationRuleMatch — Rule Execution Provenance**: When `CorrelationRuleEngine` produces a positive match, `CorrelationEventConsumer` immediately persists a `CorrelationRuleMatch` record within the same `UnitOfWork` transaction. This records **which rule triggered**, **which cluster it produced or contributed to**, **the confidence score** at the moment of evaluation, and **the precise signals that satisfied each condition** via `evidence_json`. Without this table a cluster exists but its creation rationale is opaque — with it, any SOC analyst or auditor can answer: *"Rule X matched at confidence 0.87 using signals A, B, C, creating Cluster Y at 14:32 UTC."*

---

## 3. Events Consumed

The Correlation Engine acts as a downstream consumer for key platform signals. All events are handled by `CorrelationEventConsumer`:

1. `finding.created` / `finding.updated`: Analyzes new vulnerability exposures.
2. `alert.received`: Examines external detection alerts.
3. `threat.ioc_added`: Matches newly ingested indicator items against active asset IPs.
4. `validation.failed` (Purple Team): Identifies active control gaps.

---

## 4. Events Produced

The Correlation Engine produces outbox events staged atomically within `UnitOfWork` transactions:

1. `correlation.cluster_created`: Staged when a new cluster is registered.
2. `correlation.cluster_escalated`: Staged when a cluster score crosses the critical threshold.
3. `correlation.incident_automated`: Staged when an incident is successfully spawned.

---

## 5. Correlation Rule Architecture

Rules are written as structured JSON expressions and processed via a recursive evaluator:

```json
{
  "operator": "AND",
  "conditions": [
    {
      "signal": "finding.cve_match",
      "operator": "IN",
      "value": "threat.ioc_cves"
    },
    {
      "signal": "asset.exposure_level",
      "operator": "GT",
      "value": 0.7
    },
    {
      "signal": "purple_team.validation_status",
      "operator": "EQUALS",
      "value": "FAILED"
    }
  ]
}
```

- **Execution Flow**: When a new signal arrives, `CorrelationEventConsumer` loads context, then delegates to `CorrelationRuleEngine` which queries matching parameters (e.g., pulling active CVEs for the target host asset) and runs the logical evaluation.

---

## 6. Signal Weighting Architecture

The priority score $S$ for a `CorrelationCluster` is calculated using a weighted model:

$$S = w_{\text{asset}} \cdot C_{\text{asset}} + w_{\text{finding}} \cdot \max(\text{CVSS}) + w_{\text{fabric}} \cdot F_{\text{confidence}} - w_{\text{risk}} \cdot R_{\text{accepted}}$$

Where:
- $C_{\text{asset}}$: Asset Criticality (0 to 10).
- $F_{\text{confidence}}$: Fabric score propagated down path edges (0 to 1).
- $R_{\text{accepted}}$: Deduction weight if active risk acceptance exists (0 to 5).
- $w_{x}$: Normalized domain weights.

> **Modification 5 — Score Explainability**: The `unified_score` scalar is now accompanied by `score_breakdown_json`, storing each weighted component individually. Example:
> ```json
> {
>   "asset": 4.5,
>   "finding": 2.8,
>   "fabric": 1.7,
>   "risk_adjustment": -0.5
> }
> ```
> SOC analysts querying *"Why is this cluster Critical?"* receive a transparent, component-level answer rather than an opaque numeric score. The `CorrelationAggregatorService` populates this field on every score recalculation.

---

## 7. Exposure Clustering Design

Clustering groups findings and alerts targeting the same topological graph zone:
- **Grouping Anchor**: Assets belonging to the same network sub-segment or owning scope.
- **Topological Clustering**: Triggers path traversals to group assets linked by high-priority edges (e.g. adjacent hosts on an active path).
- **Fingerprint Derivation**: The cluster fingerprint is computed as `SHA-256(sorted(asset_id + signal_ids))`, ensuring idempotent cluster creation across repeated event deliveries.
- **Cluster Closure**: When the root incident is closed, all associated signal nodes in the cluster transition to a resolved state, and a `cluster_resolved` history record is written.

---

## 8. Repository Changes Required

1. **`CorrelationRepository`**:
   - Save and query rules, clusters, signals, and history records.
   - Support `find_active_rules()`, `list_clusters_by_tenant()`, `find_cluster_by_fingerprint(tenant_id, fingerprint)`, and `add_signal_to_cluster()`.
2. **`AssetRepository` / `FindingRepository`**:
   - Expose optimized batch query join helpers to load correlated states in a single round-trip.

---

## 9. API Endpoints Required

- `GET /api/v1/correlation/rules`: List all active rules.
- `POST /api/v1/correlation/rules`: Create a new correlation rule.
- `GET /api/v1/correlation/clusters`: List all active clusters.
- `GET /api/v1/correlation/clusters/{cluster_id}`: Retrieve detailed cluster mappings, correlated signals, score breakdown, and history timeline.
- `GET /api/v1/correlation/clusters/{cluster_id}/history`: Return the full `CorrelationHistory` audit trail for a cluster.
- `POST /api/v1/correlation/clusters/{cluster_id}/escalate`: Manually escalate a cluster to a critical incident.

---

## 10. Frontend Views Required

1. **Correlation Rules Dashboard**:
   - Rule editor supporting condition definitions.
   - List view showing active statuses and priorities.
2. **Correlation Clusters Viewer**:
   - Summary view showing asset, score, score breakdown panel (per-component weights), and related signals.
   - Graphical timeline showing the sequence of correlated signal arrivals and cluster history events.
   - "Escalate to Incident" action buttons.
3. **Cluster History Panel**:
   - Chronological audit trail of all `CorrelationHistory` events for a selected cluster.
   - Filterable by `event_type` (e.g. show only escalation events).

---

## Architectural Modification Summary

| # | Modification | Rationale |
|---|---|---|
| 1 | `CorrelationHistory` table | Immutable audit trail of cluster state transitions |
| 2 | `fingerprint` + `UniqueConstraint` on `CorrelationCluster` | Prevents duplicate cluster generation from identical signals |
| 3 | `CorrelationClusterSignal` polymorphic table replaces `ARRAY(UUID)` | Scales to any future signal domain without schema changes |
| 4 | `CorrelationEventConsumer` service | Decouples event orchestration from correlation logic |
| 5 | `score_breakdown_json` on `CorrelationCluster` | SOC explainability — per-component score transparency |
| 6 | `CorrelationRuleMatch` table | Persists rule execution provenance — which rule matched, which cluster it created, at what confidence, using which signals |

---

## 11. Domain Package Structure

The Unified Correlation Engine will be implemented as a **dedicated domain package**, isolating all correlation concerns from the existing flat `services/` layer. This follows the principle of domain cohesion — all models, schemas, repository logic, business services, API routes, events, and validation for the correlation domain reside in a single importable package.

```
backend/src/app/domains/correlation/
│
├── models.py                          # SQLAlchemy ORM models
├── schemas.py                         # Pydantic request/response schemas
├── repository.py                      # CorrelationRepository (UnitOfWork-integrated)
├── service.py                         # CorrelationService (top-level orchestration facade)
│
├── correlation_rule_engine.py         # Rule evaluation logic
├── correlation_aggregator_service.py  # Score aggregation + fingerprint computation
├── correlation_incident_bridge.py     # Incident creation/escalation integration
├── correlation_event_consumer.py      # Inbound event handler + pipeline orchestrator
│
├── routes.py                          # FastAPI router (mounted at /api/v1/correlation/)
├── events.py                          # Outbox event definitions and payload builders
├── exceptions.py                      # Domain-specific exceptions
└── validators.py                      # Rule expression validators + input sanitizers
```

### File Responsibilities

#### `models.py`
Declares all six SQLAlchemy ORM models:
- `CorrelationRule` (with `rule_matches` relationship)
- `CorrelationCluster` (with `fingerprint`, `score_breakdown_json`, `signals`, `history`, `rule_matches` relationships)
- `CorrelationClusterSignal` (polymorphic signal table)
- `CorrelationHistory` (immutable audit trail)
- `CorrelationRuleMatch` (rule execution provenance)

Imported by Alembic via `Base.metadata` alongside all other domain models.

#### `schemas.py`
Pydantic v2 schemas for API serialization and validation:
- `CorrelationRuleCreate`, `CorrelationRuleResponse`
- `CorrelationClusterResponse` (includes `score_breakdown_json`, signals list, history summary)
- `CorrelationClusterSignalResponse`
- `CorrelationHistoryResponse`
- `ClusterEscalateRequest`

#### `repository.py`
`CorrelationRepository` — the single persistence boundary for all correlation data. Registered with `UnitOfWork`. Exposes:
- `find_active_rules(tenant_id)`
- `list_clusters_by_tenant(tenant_id)`
- `find_cluster_by_fingerprint(tenant_id, fingerprint)` — used for idempotent upsert
- `add_signal_to_cluster(cluster_id, signal_type, signal_id)`
- `append_history(cluster_id, event_type, details)`
- `save_rule_match(rule_id, cluster_id, confidence, evidence)` — persists `CorrelationRuleMatch` within the transaction
- `list_rule_matches_for_cluster(cluster_id)` — used by API to return rule provenance
- `save_rule(rule)`, `save_cluster(cluster)`

#### `service.py`
`CorrelationService` — the public facade consumed by `routes.py` and external callers (e.g. `IncidentService`). Delegates internally to the four specialist services. Does not contain rule evaluation or aggregation logic directly.

#### `correlation_rule_engine.py`
Stateless recursive evaluator for JSON rule expressions. Accepts a signal context dict and a list of `CorrelationRule` ORM objects. Returns a list of matched rules with confidence scores. No database I/O — receives pre-loaded data from `CorrelationEventConsumer`.

#### `correlation_aggregator_service.py`
Responsible for:
- Computing `fingerprint = SHA-256(sorted(asset_id + signal_type + signal_id))`
- Upserting `CorrelationCluster` via `find_cluster_by_fingerprint`
- Recalculating `unified_score` and `score_breakdown_json` using the weighted formula
- Writing signals to `CorrelationClusterSignal`

#### `correlation_incident_bridge.py`
Responsible for:
- Packaging correlated signal evidence
- Calling `IncidentService.create_or_sync_incident` via the shared `UnitOfWork`
- Updating `associated_incident_id` on the cluster
- Staging `correlation.incident_automated` outbox event

#### `correlation_event_consumer.py`
Celery task entrypoint and orchestration layer. Handles:
- `finding.created` / `finding.updated`
- `alert.received`
- `threat.ioc_added`
- `validation.failed`

Pipeline per event:
1. Load full context from repositories
2. Invoke `CorrelationRuleEngine`
3. Invoke `CorrelationAggregatorService`
4. Write `CorrelationHistory` record within the same `UnitOfWork`
5. Conditionally invoke `CorrelationIncidentBridge` if score threshold crossed
6. Stage outbox events

#### `routes.py`
FastAPI `APIRouter` mounted at `/api/v1/correlation/`. Declares all endpoints defined in Section 9. Depends on `CorrelationService` via FastAPI dependency injection. Enforces tenant scoping via the shared `get_current_tenant` dependency.

#### `events.py`
Defines outbox event type constants and payload builder functions:
- `CLUSTER_CREATED = "correlation.cluster_created"`
- `CLUSTER_ESCALATED = "correlation.cluster_escalated"`
- `INCIDENT_AUTOMATED = "correlation.incident_automated"`
- `build_cluster_created_payload(cluster)` → `dict`
- `build_cluster_escalated_payload(cluster, previous_score)` → `dict`

Consumed by `correlation_event_consumer.py` and `correlation_incident_bridge.py`.

#### `exceptions.py`
Domain-scoped exception classes:
- `CorrelationRuleNotFound(cluster_id)`
- `CorrelationClusterNotFound(cluster_id)`
- `DuplicateClusterFingerprintError(fingerprint)` — raised when a concurrent upsert race is detected
- `InvalidRuleExpressionError(expression, reason)`
- `ClusterEscalationError(cluster_id, reason)`

#### `validators.py`
Input validation utilities decoupled from Pydantic schemas:
- `validate_rule_expression(expression: dict)` — recursively validates JSON rule structure before persistence
- `validate_signal_type(signal_type: str)` — rejects unknown signal discriminator values
- `validate_fingerprint_input(asset_id, signals)` — ensures fingerprint inputs are well-formed before SHA-256 computation

### Integration Points

| Integration | Mechanism |
|---|---|
| `UnitOfWork` | `CorrelationRepository` registered alongside existing repositories |
| Alembic migrations | `models.py` imported via `Base.metadata`; new migration script generated |
| Outbox relay | Events staged in `outbox_events` table within the existing relay pipeline |
| Celery workers | `CorrelationEventConsumer` tasks registered in `worker.py` task registry |
| Existing `correlations.py` router | Replaced by `routes.py`; stub router retired |
| `IncidentService` | Called by `CorrelationIncidentBridge` via shared `UnitOfWork` session |
