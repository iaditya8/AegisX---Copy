# AegisX Intelligence Depth Audit

This audit evaluates the depth of intelligence, correlation, and autonomy implemented across all AegisX domains.

---

## 1. Core Classifications

### Which domains are truly operational?
- **Asset, Finding, Alert, Exposure, Incident, Remediation, and Purple Team Emulation** are truly operational. They directly govern the lifecycle of platform security objects, manage state transitions, execute scans, and interact with the user via API and frontend dashboards.

### Which domains are CRUD wrappers?
- **Threat Intelligence** (IOCs, Actors, Campaigns) and **Risk Acceptance** are primarily CRUD wrappers. They provide structured PostgreSQL storage and basic validation endpoints, but do not execute logical reasoning on their own.

### Which domains perform actual reasoning?
- **Security Intelligence Graph**, **Unified Security Intelligence Fabric**, and **Security Posture** perform actual reasoning. They construct topological trees, propagate confidence metrics across network topologies, and compute posture drifts.

### Which domains generate decisions autonomously?
- **Autonomous Security Planning**, **Security Decision**, and **Purple Team Emulation** generate decisions autonomously. They compute cost-to-benefit tradeoff matrices, schedule emulation validation sequences, and generate optimal roadmap initiatives.

### Which domains merely store information?
- **Governance (GRC)** and **Threat Intelligence** serve primarily to store reference frameworks and external IOC feeds for lookup by correlative domains.

---

## 2. Intelligence Depth Scores

Every platform domain is scored based on its peak intelligence capability:

| Domain | Peak Score | Reasoning / Code-Based Evidence |
| :--- | :--- | :--- |
| **Asset** | **CRUD** | Manages basic asset fields (host, IP, scope, criticality) via database tables. |
| **Finding** | **CRUD** | Stores vulnerabilities and misconfigurations linked to assets. |
| **Alert** | **CRUD** | Ingests and registers external warning messages. |
| **Exposures** | **Correlative** | Traverses finding and alert associations to correlate exposure paths. |
| **Threat Intelligence** | **CRUD** | Reference feed store for external IOCs and campaign profiles. |
| **Security Graph** | **Analytical** | Employs network topological traversals and shortest path algorithms. |
| **Incident Management** | **Analytical** | Groups evidence and correlates alerts to build unified analyst cases. |
| **Risk Acceptance** | **CRUD** | Manages temporary vulnerability bypass approvals. |
| **Remediation & SLA** | **CRUD** | Tracks due dates and exception policies. |
| **Threat Hunting** | **Correlative** | Correlates IOCs and attack techniques against asset and finding databases. |
| **Intelligence Fabric** | **Intelligent** | Propagates confidence scores across graph paths using decay multipliers. |
| **Security Posture** | **Analytical** | Calculates posture drift against historical baselines. |
| **Security Decision** | **Intelligent** | Employs cost-benefit matrices to recommend mitigation trade-offs. |
| **Security Program** | **Correlative** | Connects strategic initiatives to posture metrics and KPIs. |
| **Purple Team Emulation** | **Autonomous** | Schedules validation checks, executes scans, and records findings. |
| **Autonomous Planning** | **Autonomous** | Computes dependency-ordered security roadmaps and sequences. |

---

## 3. Depth Layer Definitions

1. **CRUD**: Basic CRUD storage, schema validation, and database storage.
2. **Analytical**: Conducts mathematical scoring, graph pathfinding, and drift detection.
3. **Correlative**: Evaluates relationships between distinct entities (e.g. mapping findings to attack paths).
4. **Intelligent**: Propagates context-aware security intelligence and performs tradeoff optimization.
5. **Autonomous**: Orchestrates execution loops, validates states, and structures roadmaps without manual triggers.
