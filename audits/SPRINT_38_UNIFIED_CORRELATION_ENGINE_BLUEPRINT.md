# Sprint 38: Unified Correlation Engine Blueprint

This document details the architectural design for the AegisX **Unified Correlation Engine** to be implemented in Sprint 38. The design reuses the existing database repositories, transactional `UnitOfWork` lifecycle, Security Graph path traversals, Intelligence Fabric propagation weights, and outbox event streams.

---

## 1. Services Required

To enable correlation processing without coupling, three new services are introduced:

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
  - Outputs a consolidated `CorrelationClusterRecord`.

### C. `CorrelationIncidentBridge` (`correlation_incident_bridge.py`)
- **Purpose**: Automates incident creation and escalation based on correlation engine outcomes.
- **Core Operations**:
  - Packages correlated signals into a unified case evidence collection.
  - Calls `IncidentService.create_or_sync_incident` via the `UnitOfWork`.

---

## 2. Database Models Required

Two new persistent database tables are required to store rules and cluster states.

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
```

### B. `CorrelationCluster` (`models.py`)
```python
class CorrelationCluster(Base, TenantOwnedMixin, AuditMixin):
    __tablename__ = "correlation_clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    unified_score = Column(Float, default=0.0)
    status = Column(String(50), default="open")  # open, triaged, closed
    correlated_finding_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    correlated_alert_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    correlated_ioc_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    associated_incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True)
```

---

## 3. Events Consumed

The Correlation Engine acts as a downstream consumer for key platform signals:

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

- **Execution Flow**: When a new signal arrives, the engine queries matching parameters (e.g., pulling active CVEs for the target host asset) and runs the logical evaluation.

---

## 6. Signal Weighting Architecture

The priority score $S$ for a `CorrelationCluster` is calculated using a weighted model:

$$S = w_{\text{asset}} \cdot C_{\text{asset}} + w_{\text{finding}} \cdot \max(\text{CVSS}) + w_{\text{fabric}} \cdot F_{\text{confidence}} - w_{\text{risk}} \cdot R_{\text{accepted}}$$

Where:
- $C_{\text{asset}}$: Asset Criticality (0 to 10).
- $F_{\text{confidence}}$: Fabric score propagated down path edges (0 to 1).
- $R_{\text{accepted}}$: Deduction weight if active risk acceptance exists (0 to 5).
- $w_{x}$: Normalized domain weights.

---

## 7. Exposure Clustering Design

Clustering groups findings and alerts targeting the same topological graph zone:
- **Grouping Anchor**: Assets belonging to the same network sub-segment or owning scope.
- **Topological Clustering**: Triggers path traversals to group assets linked by high-priority edges (e.g. adjacent hosts on an active path).
- **Cluster Closure**: When the root incident is closed, all associated finding and alert nodes in the cluster transition to a resolved state.

---

## 8. Repository Changes Required

1. **`CorrelationRepository`**:
   - Save and query rules and clusters.
   - Support `find_active_rules()` and `list_clusters_by_tenant()`.
2. **`AssetRepository` / `FindingRepository`**:
   - Expose optimized batch query join helpers to load correlated states in a single round-trip.

---

## 9. API Endpoints Required

- `GET /api/v1/correlation/rules`: List all active rules.
- `POST /api/v1/correlation/rules`: Create a new correlation rule.
- `GET /api/v1/correlation/clusters`: List all active clusters.
- `GET /api/v1/correlation/clusters/{cluster_id}`: Retrieve detailed cluster mappings and correlated signals.
- `POST /api/v1/correlation/clusters/{cluster_id}/escalate`: Manually escalate a cluster to a critical incident.

---

## 10. Frontend Views Required

1. **Correlation Rules Dashboard**:
   - Rule editor supporting condition definitions.
   - List view showing active statuses and priorities.
2. **Correlation Clusters Viewer**:
   - Summary view showing asset, score, and related signals (findings, alerts, IOCs).
   - Graphical timeline showing the sequence of correlated signal arrivals.
   - "Escalate to Incident" action buttons.
