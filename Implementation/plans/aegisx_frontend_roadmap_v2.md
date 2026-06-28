# AegisX Frontend Roadmap V2 — Product-Centric Architecture Review

This document presents the product-centric frontend redesign and architectural review for AegisX. It replaces page-centric dashboards with integrated workflow workspaces, aligning the frontend experience directly with AegisX's core backend graph correlation, risk quantification, and decision optimization systems.

---

# Executive Summary

The initial frontend roadmap for AegisX mirrored the backend service architecture, leading to modular screens (such as separate lists for resilience, risk, GRC, and planning). This layout creates cognitive friction, requiring security architects and SOC managers to switch contexts repeatedly to complete standard triage workflows.

This review defines AegisX's primary identity as a **Security Decision Intelligence Platform** and introduces a flagship **Unified Security Intelligence Workspace**. This workspace integrates the entire pipeline from asset discovery to risk modeling, decision tradeoff commitments, and autonomous execution. The revised sprint roadmap (Sprints 38–47) is restructured around product capabilities, analyst productivity, and collaborative security storytelling, preparing AegisX for enterprise SaaS readiness.

---

# Product Identity

### The Primary Identity: **Security Decision Intelligence Platform**

AegisX is not a simple scanner (Attack Surface Management), nor a static log collector (Exposure Management). Its unique value lies in its capability to translate technical risk signals into business decisions and execute remediation roadmaps.

```
                  ┌─────────────────────────────────────┐
                  │ Technical Signals (Assets/Findings) │
                  └──────────────────┬──────────────────┘
                                     │ (Sprints 1-23)
                                     ▼
                  ┌─────────────────────────────────────┐
                  │  Contextual Graph (Threats/GRC)     │
                  └──────────────────┬──────────────────┘
                                     │ (Sprints 24-34)
                                     ▼
                  ┌─────────────────────────────────────┐
                  │    Decision Intelligence (FAIR/AI)  │
                  └──────────────────┬──────────────────┘
                                     │ (Sprints 35-37.5)
                                     ▼
                  ┌─────────────────────────────────────┐
                  │     Autonomous Remediation (Fabric) │
                  └─────────────────────────────────────┘
```

### Architectural Justification
1. **The Graph as a Correlator (Sprint 34)**: Links technical findings to GRC assessments, threat profiles, and plans.
2. **FAIR Loss Quantification (Sprints 26/30)**: Translates vulnerabilities into monetary impact models (Annual Loss Expectancy).
3. **Tradeoff Modeling (Sprint 35)**: Maps mitigation alternatives based on cost vs risk reduction.
4. **Autonomous Milestones & Fabric Propagation (Sprints 36 & 37)**: Organizes task sequences and propagates confidence metrics.

AegisX acts as a **decision calculator** and **execution planner** for security leaders.

---

# Core Workflow

The central end-to-end user workflow is:

$$\text{Asset Discovery} \longrightarrow \text{Finding Triage} \longrightarrow \text{Graph Correlation} \longrightarrow \text{FAIR Risk Modeling} \longrightarrow \text{Decision Tradeoff} \longrightarrow \text{Autonomous Plan} \longrightarrow \text{Fabric Execution}$$

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Discovery│───▶│ Finding │───▶│ Graph   │───▶│ Risk     │───▶│ Decision │───▶│ Execution│
│ (Assets)│     │(Triage) │     │(Context)│     │(Impact)  │     │(Tradeoff)│     │(Fabric)  │
└─────────┘     └─────────┘     └─────────┘     └──────────┘     └──────────┘     └──────────┘
```

1. **Discovery & Triage**: Continuous scanning registers an asset and generates a finding.
2. **Graph Correlation**: The finding is mapped to active threats, affected compliance controls, and related assets.
3. **Risk Modeling**: A FAIR simulation projects the financial impact of the exposure.
4. **Decision Tradeoff**: The system recommends remediations, displaying the cost vs risk-reduction tradeoff.
5. **Execution**: The approved decision is converted into planning milestones and propagated across the unified fabric nodes.

---

# User Journeys

### 1. Security Analyst

```
[Asset/Finding Trigger] ──▶ [Inspect Graph Topology] ──▶ [Review Playbook Recommendations] ──▶ [Initiate Remediation Plan]
```

- **Trigger**: Receives an alert showing a new active finding (e.g. exposed AD interface).
- **Investigation**: Opens the workspace to view the asset's graph topology and determine if public access paths exist.
- **Analysis**: Reviews threat intelligence fusion scores and GRC control failures linked to the finding.
- **Decision**: Evaluates the recommended playbook mitigation options.
- **Action**: Confirms the mitigation action, moving it to the active planning pipeline.

### 2. Security Architect

```
[Vulnerability Map Trigger] ──▶ [Analyze Multi-hop Attack Paths] ──▶ [Simulate Control Mitigation] ──▶ [Approve System Decision]
```

- **Trigger**: Reviews the scope's overall graph topology.
- **Investigation**: Identifies multi-hop paths linking external assets to internal databases.
- **Analysis**: Cross-references missing GRC controls and active threat actor profiles.
- **Decision**: Runs simulations on proposed mitigations (such as isolating a subnet).
- **Action**: Commits the decision, automatically updating the unified fabric propagation channels.

### 3. SOC Manager

```
[Queue Congestion Trigger] ──▶ [Analyze MTTR Timelines] ──▶ [Prioritize High-Risk Gaps] ──▶ [Assign Planning Milestones]
```

- **Trigger**: Receives an alert showing an MTTR SLA target warning.
- **Investigation**: Opens the analytics console to view active analyst queues.
- **Analysis**: Reviews which open finding categories account for the queue bottleneck.
- **Decision**: Determines which findings should be triaged or scheduled for remediation.
- **Action**: Optimizes the plan execution sequence and adjusts analyst assignments.

### 4. CISO

```
[Financial Exposure Trigger] ──▶ [Review Loss Expectancy Models] ──▶ [Assess Budget Tradeoffs] ──▶ [Generate Audit Reports]
```

- **Trigger**: Prepares for an board meeting.
- **Investigation**: Reviews the organization's annualized loss expectancy forecasts.
- **Analysis**: Analyzes the financial return on security investments (ROSI) based on proposed decisions.
- **Decision**: Approves the security budget allocation for the next quarter.
- **Action**: Generates GRC audit readiness reports.

---

# Problems In Current Roadmap

### 1. Dashboard-Driven Design Problems
The previous roadmap proposed separate pages for Resilience, Risk, GRC, and SOC Analytics. This layout isolates related data. For example, risk loss expectancy numbers are useless unless viewed alongside GRC compliance gaps and pending security decisions.

### 2. Navigation Problems
To resolve an exposure, an analyst would need to:
1. Search for the asset in the **Assets List**.
2. Click to open the **Findings List** to view vulnerabilities.
3. Open the **Graph Workspace** to map dependencies.
4. Navigate to the **Decisions Queue** to approve a remediation.
5. Switch to the **Planning View** to check the schedule.

This context switching creates cognitive load and slows triage times.

### 3. Workflow Breaks
The backend links components dynamically (such as updating fabric nodes when a plan milestone is closed). In the previous frontend design, these systems were displayed as disconnected pages. This makes it difficult for users to track how a single configuration change propagates across the platform.

---

# Workspace Architecture

Instead of independent page routes, the platform is redesigned around **Dynamic Workspaces**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        AegisX Unified Console                          │
├────────────────────────────────────────────────────────────────────────┤
│  [Scope: Global CIDR]                                                  │
│                                                                        │
│   ┌───────────────────────────┐      ┌──────────────────────────────┐  │
│   │  EXPOSURE WORKSPACE       │      │  DECISION & PLANNING         │  │
│   │                           │      │  WORKSPACE                   │  │
│   │  * Asset Directory        │      │                              │  │
│   │  * Findings Triage        │─────▶│  * Recommendations Queue     │  │
│   │  * Attack Path SVGs       │      │  * Tradeoff Plots            │  │
│   │                           │      │  * Milestone Gantt Charts    │  │
│   └───────────────────────────┘      └──────────────────────────────┘  │
│                 │                                    ▲                 │
│                 ▼                                    │                 │
│   ┌───────────────────────────┐                      │                 │
│   │  INTELLIGENCE WORKSPACE   │                      │                 │
│   │                           │                      │                 │
│   │  * Threat Intel Streams   │──────────────────────┘                 │
│   │  * GRC Control Mappings   │                                        │
│   │  * Knowledge Playbooks    │                                        │
│   └───────────────────────────┘                                        │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Exposure Workspace**: Combines scopes, assets, vulnerability findings, and graph topologies into a single view.
2. **Intelligence Workspace**: Displays threat feeds, playbook recommendations, and GRC controls.
3. **Decision & Planning Workspace**: Lists recommendations, tradeoff scatterplots, and Gantt charts.
4. **Executive Workspace**: Displays CISO metrics, financial risk curves, and report builders.

---

# Unified Security Intelligence Workspace

The flagship **Unified Security Intelligence Workspace** integrates the platform's features into a single, cohesive interface.

### Layout Architecture
- **Interactive Topographic Panel (Left - 60% Width)**: 
  - Displays the SVG/Canvas graph topology, focusing on the selected scope. 
  - Nodes represent Assets (blue), Findings (red), Threats (amber), and Decisions (purple). 
  - Attack paths and fabric routes are highlighted with animated connectors.
- **Context Details Drawer (Right - 40% Width)**:
  - Dynamically updates based on the selected node or path.
  - **Tab 1: Telemetry**: Active asset details, technologies, open ports, and raw findings.
  - **Tab 2: Threat & GRC**: Associated threat actor profiles, playbooks, and missing GRC framework controls.
  - **Tab 3: Risk Impact**: FAIR annual loss distribution curve and MTTR metrics.
  - **Tab 4: Remediation**: Decision tradeoff metrics and plan milestone timelines.

### Interactive Traversal Example
1. Selecting an **Asset Node** updates the drawer to display open vulnerabilities and RTO/RPO targets.
2. Selecting a **Vulnerability finding** on the asset displays the linked GRC controls and threat intelligence fusion scores.
3. Selecting a **playbook remediation** displays the financial cost vs risk-reduction tradeoff.
4. Clicking **Commit** automatically schedules the remediation, adds it to the Gantt chart, and updates the graph paths.

---

# Revised Sprint Roadmap

The sprint roadmap is restructured to focus on **user workflows and product capabilities** rather than individual backend endpoints.

---

### Sprint 38: Core Workspace Foundation

#### Sprint Objective
Implement authentication, the layout grid, and the global scope context selector.

#### User Personas
- **All Personas**: Navigate the primary workspaces.

#### Product Value
Establishes the platform's visual layout and data hydration architecture.

#### Screens
- **Unified Workspace Layout**: The main wrapper displaying the sidebar, topbar, and core workspace routes.
- **Login Portal**: Secure access inputs.

#### Components
- **`WorkspaceWrapper`**: Layout grid isolating workspaces.
- **`ScopeDropdown`**: Context switcher in header.
- **`RouteGuard`**: Role-based access controller.

#### State Management
- Zustand store managing the active scope context and authentication state.

#### API Integrations
- `/api/v1/auth/login` & `/api/v1/auth/refresh`.

#### UX & Accessibility
- Accessible routing transitions and loading screens.

#### Testing Requirements
- Vitest: Verify token injection and RouteGuard routing logic.

#### Acceptance Criteria
- Access token injection and RouteGuard redirects function correctly.

---

### Sprint 39: Core Asset & Triage Workspace

#### Sprint Objective
Implement the basic Exposure Workspace to support asset management and finding triage workflows.

#### User Personas
- **Security Analyst**: Triages findings.
- **SOC Manager**: Reviews scan runs.

#### Product Value
Replaces independent list pages with a unified view of scopes, assets, and findings.

#### Screens
- **Exposure Workspace View**: Split layout containing the asset list and finding detail pane.
- **Scan Runner Control**: Popover to trigger scan runs.

#### Components
- **`AssetTable`**: Custom grid with inline filter options.
- **`FindingInspector`**: Drawer component displaying details of selected findings.
- **`TriageButtons`**: Action buttons (Acknowledge, Resolve, Suppress).

#### State Management
- React Query managing scope asset lists and finding caches.

#### API Integrations
- `/api/v1/scopes`, `/api/v1/scopes/{id}/assets`, `/api/v1/findings`.

#### UX & Accessibility
- Table elements support keyboard navigation and include status labels.

#### Testing Requirements
- Vitest & MSW: Test finding status transitions.

#### Acceptance Criteria
- Triaging a finding updates the status tag instantly.

---

### Sprint 40: SOC Queues & Resilience Monitor

#### Sprint Objective
Implement the team performance and resilience tracking views inside the SOC and Executive dashboards.

#### User Personas
- **SOC Manager**: Monitors analyst queues and MTTR.
- **Security Analyst**: Monitors RTO/RPO targets.

#### Product Value
Provides metrics showing how technical exposures affect business resilience.

#### Screens
- **Analytics Workspace**: Metrics dashboard displaying analyst queues and resilience targets.

#### Components
- **`MTTRHistogram`**: Custom SVG histogram plotting ticket close rates.
- **`ResilienceProgress`**: Progress rings showing RTO/RPO compliance percentages.
- **`AnalystQueueList`**: Real-time list showing active workloads.

#### State Management
- React Query caching for SOC and resilience endpoints.

#### API Integrations
- `/api/v1/cyber-resilience`, `/api/v1/soc-analytics`.

#### UX & Accessibility
- Progress rings include text labels and adapt to screen resizing.

#### Testing Requirements
- Vitest: Mock queue status updates.

#### Acceptance Criteria
- Resilience and SOC analytics dashboards render correctly inside scope boundaries.

---

### Sprint 41: FAIR Risk Modeling & GRC Audit Console

#### Sprint Objective
Implement GRC audit workspaces and financial risk quantification modules.

#### User Personas
- **GRC Analyst**: Manages framework compliance.
- **CISO**: Reviews risk metrics.

#### Product Value
Translates technical vulnerabilities into compliance scores and financial loss ranges.

#### Screens
- **Audit Console Workspace**: Framework dashboard displaying assessments, gaps, and evidence loaders.

#### Components
- **`FAIRLossChart`**: SVG line chart displaying Annual Loss Expectancy distributions.
- **`ComplianceChecklist`**: Interactive accordion showing control requirements.
- **`EvidenceLoader`**: Upload container showing file status logs.

#### State Management
- Zustand store managing evidence upload queues and progress states.

#### API Integrations
- `/api/v1/cyber-risk-quantification`, `/api/v1/governance-risk-compliance`.

#### UX & Accessibility
- Drag-and-drop targets support keyboard file selection.

#### Testing Requirements
- Playwright: Test file uploads and verify checklist expansion states.

#### Acceptance Criteria
- Uploading evidence updates the compliance score dynamically.

---

### Sprint 42: Interactive Threat & Knowledge Workspace

#### Sprint Objective
Integrate real-time threat intelligence streams and playbook recommendations.

#### User Personas
- **Security Analyst**: Monitors threats and playbooks.

#### Product Value
Provides analysts with threat context and step-by-step mitigation playbooks.

#### Screens
- **Intelligence Workspace View**: Real-time threat streams and playbook detail views.

#### Components
- **`ThreatStream`**: Live threat event stream list.
- **`PlaybookAccordion`**: Renders playbook markdown and task checklists.
- **`ThreatFusionBadge`**: Visual badge displaying alert confidence metrics.

#### State Management
- React Query caching threat and playbook records.

#### API Integrations
- `/api/v1/threat-intelligence`, `/api/v1/security-knowledge`.

#### UX & Accessibility
- Live feeds include pause options to prevent focus loss during triage.

#### Testing Requirements
- Vitest: Verify markdown rendering and test threat fusion actions.

#### Acceptance Criteria
- Fusing a threat transitions its status to FUSED and displays the updated confidence rating.

---

### Sprint 43: Security Relationship Graph Visualizer

#### Sprint Objective
Implement the interactive relationship topology map displaying assets, findings, threats, GRC, and playbooks.

#### User Personas
- **Security Architect**: Analyzes multi-hop attack vectors.
- **Security Analyst**: Traverses relationships.

#### Product Value
Replaces isolated data lists with a connected graph view of assets and vulnerabilities.

#### Screens
- **Topology Graph Canvas**: Interactive node-link visualizer.

#### Components
- **`GraphCanvas`**: Custom SVG/Canvas renderer.
- **`RelationshipControl`**: Filter bar to toggle node layers.
- **`PathHighlighter`**: Tool to search and highlight paths.

#### State Management
- Zustand store controlling zoom levels, selected nodes, and active filters.

#### API Integrations
- `/api/v1/security-intelligence-graph`.

#### UX & Accessibility
- Full keyboard support for panning and zooming.

#### Testing Requirements
- Playwright: Test pan, zoom, and node click actions.

#### Acceptance Criteria
- Zoom and pan operations complete smoothly at 60 FPS on topologies under 1,000 nodes.

---

### Sprint 44: Decision Tradeoffs Console

#### Sprint Objective
Implement decision triage views displaying cost vs risk-reduction tradeoff analytics.

#### User Personas
- **SOC Manager**: Approves mitigations.
- **CISO**: Reviews cost/benefit metrics.

#### Product Value
Helps security leaders select mitigations by comparing costs to risk reduction.

#### Screens
- **Decisions Dashboard**: Queue display showing pending actions and tradeoff charts.

#### Components
- **`TradeoffPlot`**: Scatterplot mapping financial cost vs risk reduction.
- **`DecisionQueue`**: List showing pending recommendations.
- **`LLMAdvisoryBadge`**: Badge explaining recommendations are advisory-only.

#### State Management
- React Query managing decision state transitions.

#### API Integrations
- `/api/v1/security-decision`.

#### UX & Accessibility
- Triage actions require confirmation popups to prevent accidental mutations.

#### Testing Requirements
- Vitest: Verify tradeoff scatterplot coordinates calculation.

#### Acceptance Criteria
- Committing a decision transitions its status and displays the advisory-only warning badge.

---

### Sprint 45: Autonomous Planner & Fabric Topology

#### Sprint Objective
Implement roadmap timelines for autonomous plans and confidence routing controls for fabric nodes.

#### User Personas
- **Security Architect**: Manages fabric configurations.
- **SOC Manager**: Monitors active remediation milestones.

#### Product Value
Enables users to monitor planning milestones and unified fabric propagation channels.

#### Screens
- **Planning & Fabric Workspace**: Split view displaying Gantt charts and fabric propagation lines.

#### Components
- **`PlanningGantt`**: Renders milestone schedules (planned, active, closed).
- **`FabricFlow`**: Renders confidence propagation paths and decay values.
- **`OptimizeTrigger`**: Button panel to request sequence optimizations.

#### State Management
- React Query managing planning and fabric caches.

#### API Integrations
- `/api/v1/autonomous-security-planning`, `/api/v1/unified-security-intelligence-fabric`.

#### UX & Accessibility
- Gantt charts include keyboard focus support.

#### Testing Requirements
- Playwright: Test optimization triggers and verify Gantt chart updates.

#### Acceptance Criteria
- Triggering an optimization updates milestone positions and fabric flow values.

---

## Sprint 46: Tenant Workspaces & SSO Portal

#### Sprint Objective
Implement tenant switchers, enterprise workspace directories, and SAML/OIDC configuration panels.

#### User Personas
- **Admin**: Configures SSO and tenants.

#### Product Value
Provides multi-tenant isolation and secure authentication configurations.

#### Screens
- **Administration Portal**: Settings panel to configure SSO and tenants.

#### Components
- **`TenantSwitcher`**: Dropdown component in sidebar to switch workspaces.
- **`SSOConfigForm`**: Configuration form to manage certificates and URLs.

#### State Management
- Zustand store managing the active tenant context.

#### API Integrations
- `/api/v1/admin/tenants`, `/api/v1/admin/auth-settings`.

#### UX & Accessibility
- Context switching requires user confirmation to prevent unsaved changes.

#### Testing Requirements
- Vitest: Verify tenant switching clears query caches.

#### Acceptance Criteria
- Switching tenant context updates workspace data instantly without leaking logs.

---

## Sprint 47: Saved Whiteboards & Custom Exporters

#### Sprint Objective
Deliver saved whiteboards, custom alerting rules, and drag-and-drop PDF report layout builders.

#### User Personas
- **Security Analyst**: Saves active investigations.
- **CISO**: Builds custom dashboards and reports.

#### Product Value
Enables analysts to save investigation layouts and CISOs to export custom posture reports.

#### Screens
- **Investigations Board**: Whiteboard screen to track findings.
- **Report Designer**: Drag-and-drop dashboard to build reports.

#### Components
- **`WhiteboardCanvas`**: Drag-and-drop workspace layout.
- **`CustomExporterPanel`**: Sidebar panel displaying reporting templates.
- **`DragWidget`**: Draggable component template.

#### State Management
- Zustand store managing active whiteboard states and coordinate positions.

#### API Integrations
- `/api/v1/investigations`, `/api/v1/reports/custom`.

#### UX & Accessibility
- Drag-and-drop elements support keyboard controls.

#### Testing Requirements
- Playwright: Test drag-and-drop and custom report exports.

#### Acceptance Criteria
- Whiteboards and custom layouts can be saved and exported as PDF files.

---

# Missing Product Capabilities

1. **Security Storytelling (Attack Paths)**: The original design lacked a step-by-step layout showing how vulnerabilities are linked in multi-hop attack paths. The redesigned graph visualizer maps these relationships.
2. **Saved Investigation Whiteboards**: Analysts need a way to group related findings, assets, and threat feeds onto a single canvas. Sprint 47 adds saved whiteboards.
3. **Collaboration & Analyst Notes**: Multiple analysts need a way to collaborate on investigations. Sprint 47 adds notes and activity feeds to assets and findings.
4. **Custom Report Builders**: The previous plan limited reporting to static CSV/JSON downloads. Sprint 47 adds a drag-and-drop report layout builder.
5. **AI Copilot Interaction Center**: The platform had no chat layout for AI interactions. We recommend adding a slide-out Copilot chat drawer across all workspaces.

---

# Enterprise Readiness Assessment

| Requirement | Stage | Status | Gap Remediation |
| :--- | :--- | :--- | :--- |
| **Data Isolation** | Sprint 46 | **PARTIAL** | Enforced at route layer. Frontend needs workspace isolation context switchers to prevent split-brain leakage. |
| **Identity & SSO** | Sprint 46 | **MISSING** | No SAML/OIDC forms exist. Sprint 46 implements SSO admin settings portals. |
| **Audit Trails** | Sprint 38 | **COMPLETE** | Stored on backend. Front-end displays them in the details drawers. |
| **SLA Alerting** | Sprint 47 | **MISSING** | SOC manager needs a rules editor to trigger alerts when MTTR targets are exceeded. |
| **Evidence Management** | Sprint 41 | **COMPLETE** | Supported by GRC upload panels, enabling analysts to attach documents to compliance audits. |

---

# Final Recommendation

1. **Adopt a Workflow-Driven Workspace Architecture**: Shift from modular page screens to integrated workspaces (Exposure, Decisions, and the Unified Security Intelligence Workspace).
2. **Prioritize the Unified Workspace (Sprint 43)**: Focus on the relationship visualizer to integrate assets, findings, risks, and plans into a single view.
3. **Implement Concurrency & SSO (Sprint 46)**: Build multi-tenant switchers and SSO portals to prepare the platform for enterprise deployments.
4. **Follow the Revised Sprint Roadmap**: Execute Sprints 38–47 to progress AegisX from platform foundation to enterprise SaaS maturity.
