# AegisX Correlation Readiness Audit

This audit evaluates the feasibility, readiness, and technical constraints of implementing a platform-wide **Unified Correlation Engine** in AegisX.

---

## PART 1 — Executive Summary

### Correlation Readiness Score: **8.5/10** (Highly Ready)
- **Why**: AegisX is highly ready for a Unified Correlation Engine. All core data structures (assets, findings, exposures, threat actors, campaigns, incidents, risks) are fully backed by PostgreSQL and abstracted behind repositories. Relationships are mapped topologically in the `SecurityIntelligenceGraph` and context-propagated via `UnifiedSecurityIntelligenceFabric`. 

### Core Question: Can AegisX support a Unified Correlation Engine without major architectural refactoring?
- **Answer**: **YES**. 
- **Evidence**: The database tables (`assets`, `findings`, `exposures`, `threat_intel_iocs`, `security_intelligence_fabric_nodes`, `incidents`, `risk_acceptances`, `remediations`, `security_postures`, `security_decisions`, `purple_team_exercises`) are fully populated and linked via foreign keys or join tables. The L2 cache bootstrapping guarantees database-to-cache alignment. A correlation engine would merely need to query these existing tables, aggregate the signals, and write outputs back through the `UnitOfWork` lifecycle.

---

## PART 2 — Domain Signal Inventory

| Domain | Signals Available | Signal Quality | Correlation Value |
| :--- | :--- | :--- | :--- |
| **Assets** | Scope, Owner, Criticality, IP, Domain | **High** (Well-structured in DB) | **High** (Asset is the core anchor of all correlations) |
| **Findings** | Severity, CVSS, EPSS, Source Tool | **High** (Standardized via schemas) | **High** (Identifies exploitable points) |
| **Alerts** | Title, Host, Priority, Status | **Medium** (Varies by source feed) | **High** (Triggers real-time alerts) |
| **Exposures** | Path Length, Exposure Level, Remediation Link | **High** (Calculated on graph topology) | **High** (Estimates exploitability risk) |
| **Threat Intel** | IOC Value, Actor Name, Campaign link | **Medium** (Requires external feeds) | **High** (Contextualizes findings) |
| **Threat Hunting**| Hypothesis, Hunting Findings, IOC matches | **High** (Validated by hunts) | **Medium** (Preserves hunt outcome context) |
| **Security Graph** | Node Type, Edge Connectivity, Path Depth | **High** (Graph topology database) | **High** (Triggers path calculations) |
| **Intel Fabric** | Confidence score, Decay factors | **High** (Calculated via fabric nodes) | **High** (Weights the threat signals) |
| **Incidents** | Title, Severity, Investigation Status | **High** (Persistent records) | **High** (Correlates alerts into analyst cases) |
| **Risk** | Expiration Date, Approved By, Reason | **High** (Auditable tables) | **High** (Flags authorized vs unauthorized bypasses) |
| **GRC** | Control Mapping, Policy Coverage | **High** (Aligned in DB) | **Medium** (Checks SLA/Compliance impact) |
| **Posture** | Drift Alert, Posture Score, Risk category | **High** (Calculated profiles) | **Medium** (Measures security health trends) |
| **Decision** | Option Name, Tradeoff Cost Matrix, Net Benefit | **High** (Matrix profiles) | **Medium** (Provides remediation recommendations) |
| **Program** | Objective KPIs, Initiatives | **High** (Mapped items) | **Low** (High-level organizational planning) |
| **Purple Team** | Technique ID, Validation Status, Failed Controls | **High** (Emulation records) | **High** (Confirms if detection rules function) |

---

## PART 3 — Existing Relationships

The following entity relationships are already implemented and tracked in the database:

1. **Asset → Finding**
   - **Relationship Type**: One-to-Many
   - **Storage**: `findings.asset_id` (FK)
   - **Confidence**: 10/10
   - **Coverage Score**: 10/10

2. **Finding → Exposure**
   - **Relationship Type**: Many-to-Many (via join tables)
   - **Storage**: `exposure_findings` table
   - **Confidence**: 9/10
   - **Coverage Score**: 9/10

3. **IOC → Asset**
   - **Relationship Type**: Many-to-Many (via correlation tables)
   - **Storage**: `threat_intel_iocs` correlated to asset IPs/domains
   - **Confidence**: 8/10
   - **Coverage Score**: 8/10

4. **Incident → Evidence**
   - **Relationship Type**: One-to-Many
   - **Storage**: `incident_evidence.incident_id` (FK)
   - **Confidence**: 10/10
   - **Coverage Score**: 10/10

5. **Risk → Asset / Finding**
   - **Relationship Type**: Many-to-One
   - **Storage**: `risk_acceptances.asset_id` (FK) and `risk_acceptances.finding_id` (FK)
   - **Confidence**: 10/10
   - **Coverage Score**: 9/10

6. **Program → Posture**
   - **Relationship Type**: Correlative (via score mapping)
   - **Storage**: Service-level lookup joining posture profiles to strategic programs.
   - **Confidence**: 8/10
   - **Coverage Score**: 8/10

---

## PART 4 — Graph Readiness

### Security Intelligence Graph Capabilities
- **Node Types**: `Asset`, `Vulnerability`, `ThreatActor`, `IOC`, `Incident`.
- **Edge Types**: `RunsOn`, `Affects`, `AssociatedWith`, `EvidenceOf`.
- **Metadata**: Severity, status, confidence, tenant_id.
- **Traversal Support**: Implements breadth-first search (BFS) and depth-first search (DFS) traversals.
- **Shortest Path Support**: Fully implemented in `shortest_path` helpers.
- **Community Detection**: Enabled on graph datasets to segment subnet boundaries.
- **Risk Propagation**: Handled via the Intelligence Fabric decay algorithm.

### Graph Reuse Potential: **YES**
The Security Intelligence Graph is ready to serve as the topological foundation of the Correlation Engine. Any finding or alert generated can be placed on the graph to evaluate its proximity to critical assets.

---

## PART 5 — Event Readiness

### Produced Events
- `finding.created`, `finding.updated` (Finding Domain)
- `incident.created`, `incident.updated`, `incident.closed` (Incident Domain)
- `threat.ioc_added` (Threat Intel Domain)
- `posture.drift_detected` (Posture Domain)
- `validation.failed` (Purple Team Domain)

### Consumed Events
- `posture.drift_detected` -> Consumed by `SecurityPostureService` and `AIContextBuilder`.
- `validation.failed` -> Consumed by `RemediationService` to trigger tickets.

### Event Gaps
- `threat.ioc_added` is staged but has no real-time consumers; it is currently checked via periodic pollers in Celery workers.
- **Gaps**: A Unified Correlation Engine should consume all incoming `finding.created` and `threat.ioc_added` events in real-time to trigger instant path recalculations.

### Event Architecture Score: **8/10**

---

## PART 6 — Repository & Data Access Readiness

### Query Capabilities Implemented:
- `find_assets_by_risk()`
- `find_findings_by_asset()`
- `find_iocs_by_asset()`
- `find_open_incidents_by_asset()`

### Correlation Query Readiness: **High**
The repositories support complex joins joining Threat -> Asset -> Finding -> Risk -> Incident without excessive refactoring, as all relationships are database-backed and indexed.

---

## PART 7 — Existing Intelligence Components

1. **Exposure Mapping**
   - **Input**: Assets, findings, network edges.
   - **Processing**: Graph path traversal to identify exposable routes.
   - **Output**: Exposure paths and severity scores.
   - **Reuse**: High (Acts as the primary exploitability input).

2. **Threat Hunting Correlation**
   - **Input**: Hypotheses and IOC matches.
   - **Processing**: Matching indicator values against active asset traffic.
   - **Output**: Hunting correlation lists.
   - **Reuse**: Medium (Triggers hunts dynamically).

3. **Fabric Propagation**
   - **Input**: Graph edges and confidence scores.
   - **Processing**: Propagates scores down connected paths using decay ratios.
   - **Output**: Topologicallyweighted node priorities.
   - **Reuse**: High (Serves as the signal weighting engine).

4. **Decision Optimization**
   - **Input**: Tradeoff metrics and options.
   - **Processing**: Compares mitigation cost against risk reductions.
   - **Output**: Optimal decision selections.
   - **Reuse**: High (Recommends target responses).

---

## PART 8 — Correlation Engine Design Readiness

### What Already Exists
- Database tables and relations.
- RLS boundary enforcement.
- Outbox event staging.
- L2 cache bootstrap mechanisms.
- Shortest path graph traversals.
- Confidence scoring decay logic.

### What Is Missing
- **Correlation Rules Engine**: A service that executes rules like `IF (IOC matches Asset IP) AND (Asset has Vulnerability matching IOC CVE) AND (Purple Team validation failed for CVE) THEN (Create Critical Incident)`.
- **Signal Weighting Aggregator**: Composes threat confidence, vulnerability severity, and asset criticality into a single weight.
- **Alert Clusterer**: Groups similar correlated events to prevent analyst alert fatigue.

### Estimated Build Complexity: **Medium**
Since the data and graph layers are already persistent, multi-tenant, and verified, the Correlation Engine only needs to be built as a logical service that orchestrates queries across these domains.

---

## PART 9 — Candidate Correlation Use Cases

1. **Threat Exposure Correlation (High Value)**: Link threat actors with campaigns and vulnerable assets.
2. **Active Exploit Path Correlation**: Correlate internet-exposed assets with findings that have active public exploits.
3. **Failed Control Validation Escalation**: Escalate incidents on assets where Purple Team validations failed.
4. **GRC SLA Breach Risk Correlation**: Prioritize remediations near SLA breach dates on critical assets.
5. **Drift-Induced Exposure Correlation**: Highlight posture drift on assets that are part of critical exposure paths.
6. **IOC Traffic to Vulnerable Asset Link**: Link active IOC matches with assets hosting CVEs targeted by that IOC.
7. **Bypass Risk Re-evaluation**: Recalculate risk when an accepted bypass expires on a vulnerable host.
8. **Campaign Ingestion Triggered Scan**: Trigger hunts when a new campaign is ingested matching active techniques.
9. **Asset Criticality Shift Posture Recalc**: Re-evaluate security posture when asset criticality shifts from Low to High.
10. **Decision-Driven Remediation Ticket**: Automate ticket creation when decision tradeoffs select a specific option.

---

## PART 10 — Final Verdict

* **Is AegisX ready for a Unified Correlation Engine?** **YES**.
* **What percentage of required infrastructure already exists?** **80%** (Data models, repositories, graphs, outbox, and RLS are fully active).
* **What percentage must still be built?** **20%** (The correlation rules service and clusterer).
* **What is the largest technical blocker?** The lack of containerized sandboxing for plugins executing the scans.
* **What is the single highest-value Sprint 38 objective?** Build the **Unified Correlation Engine** to join the threat, vulnerability, and asset domains.
