# AegisX Frontend Roadmap V2.1 — Product Architecture Correction Review

This document presents the product architecture correction review (Roadmap V2.1) for AegisX. It reorganizes the frontend sprint sequence to prioritize the flagship **Unified Security Intelligence Workspace** and introduces dedicated sprints for **Executive Decision Intelligence** and the **Security Intelligence Copilot**.

---

# Executive Summary

The V2 roadmap was a significant improvement over page-centric designs, but it still delayed the flagship **Unified Security Intelligence Workspace** until Sprint 43. This delay meant that the core value proposition of AegisX as a **Security Decision Intelligence Platform** would not be experienced by users until late in the development cycle.

Roadmap V2.1 corrects this sequence. By moving the **Attack Surface & Security Intelligence Workspace (MVP)** to **Sprint 40**, we deliver immediate time-to-value. This review justifies this change, outlines the three-panel layout for the workspace, designs the new **Executive Decision Intelligence** sprint, and defines the safety boundaries for the **Security Intelligence Copilot** in Sprint 48.

---

# Product Identity

### AegisX = Security Decision Intelligence Platform

The backend (Sprints 1–37) is built to calculate risks and plan remediation roadmaps. The frontend must expose this workflow directly to the user.

- **Market Positioning**: AegisX sits above scanners and log aggregators. It acts as the **decision engine** and **execution planner** for security operations.
- **Primary User Value**: Translates technical vulnerabilities into financial impact models and structured remediation plans, helping security leaders prioritize budgets and assign tasks.

---

# Core Workflow

The primary end-to-end user workflow is:

$$\text{Asset Discovery} \longrightarrow \text{Finding Triage} \longrightarrow \text{Graph Correlation} \longrightarrow \text{Risk Quantification} \longrightarrow \text{Decision Tradeoff} \longrightarrow \text{Planning} \longrightarrow \text{Fabric Execution}$$

This workflow represents the core value of the platform.

---

# Problems In Current Roadmap

### 1. Delayed Time-to-Value
The previous V2 roadmap delayed the **Unified Security Intelligence Workspace** until Sprint 43. Up until that point, the interface would function as a series of isolated dashboards. This structure delays the product vision and prevents users from experiencing the core value proposition early in the lifecycle.

### 2. Isolated Dashboards
By building the GRC, Gaps, Resilience, and Threat modules in Sprints 40–42 before the unified graph view, the layout remains backend-module-centric. Users would need to open multiple screens and manually correlate information to perform standard investigations.

### 3. Context Fragmentation
Forcing the user to learn separate screens for risk calculations, decisions, and plans before they see how these components connect creates cognitive friction and limits initial adoption.

---

# Workspace Architecture

We define four primary workspaces to align with the core user journeys:

1. **Attack Surface & Security Intelligence Workspace (Flagship)**: The core console for analysts and architects, integrating asset inventories, attack surface change tracking, findings, threats, risks, decisions, and plans into a single screen.
2. **Executive Decision Intelligence Workspace**: A dedicated view for CISOs and executives, displaying risk curves, budget tradeoff sliders, and automated narratives.
3. **GRC & Evidence Workspace**: A workspace for GRC analysts to track framework compliance, manage control checklists, and upload evidence.
4. **Administration & SSO Workspace**: A dashboard for system administrators to manage tenants, configure SSO, and monitor audit logs.

---

# Attack Surface & Security Intelligence Workspace (MVP Design)

The MVP version of the workspace will be delivered in **Sprint 40**, immediately following the foundation and shared component sprints.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 AegisX Unified Console                                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  [Scope: Global Prod]                                               [Search Entities]  │
│                                                                                        │
│   ┌────────────────────────┐   ┌───────────────────────────┐   ┌────────────────────┐  │
│   │ LEFT PANEL             │   │ CENTER PANEL              │   │ RIGHT PANEL        │  │
│   │                        │   │                           │   │                    │  │
│   │ [Attack Surface & ASM] │   │ [Investigation Context]   │   │ [Decision Context] │  │
│   │                        │   │                           │   │                    │  │
│   │ * Asset Inventory      │   │ * Interactive SVG Graph   │   │ * Tradeoff Plot    │  │
│   │ * Unmanaged assets     │──▶│   (Asset -> Threat -> Risk)│──▶│ * Commited Plans   │  │
│   │ * Exposure Summary     │   │ * Exploit Path Highlight  │   │ * LLM Advisory     │  │
│   │                        │   │                           │   │   Warning          │  │
│   └────────────────────────┘   └───────────────────────────┘   └────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Layout Overview
A three-panel layout that integrates the platform's original recon DNA with decision intelligence, preventing page switching:

- **Left Panel (Attack Surface & ASM - 25% Width)**:
  - **Asset Inventory**: Lists all active internet-facing target hostnames, IP interfaces, and normalized services.
  - **Attack Surface Changes**: Highlights delta detections (what changed since last week, new subdomains discovered, ports opened).
  - **Open Findings**: Highlights critical vulnerability exposures and active exploit alerts.
  - **Exposure Summary**: Summarizes statistics (managed vs unmanaged assets, scores per business unit or scope context).
- **Center Panel (Investigation Context - 50% Width)**:
  - Displays an interactive SVG topology map centering on the selected asset.
  - Renders adjacent node relationships (Findings, active Threats, GRC controls).
  - Highlights critical attack paths in red.
- **Right Panel (Decision Context - 25% Width)**:
  - Displays the FAIR risk simulation results (Annualized Loss Expectancy).
  - Lists pending decision recommendations and the cost vs risk-reduction tradeoff scatterplot.
  - Displays the action confirmation buttons and active planning milestones.

### Workflow Navigation
1. **Trigger**: An analyst reviews the **Left Panel** to inspect newly discovered/changed unmanaged assets or critical findings.
2. **Analysis**: The **Center Panel** focuses on the asset, rendering its relationship graph and highlighting the attack path.
3. **Evaluation**: The **Right Panel** displays the financial risk impact and recommended mitigations.
4. **Action**: The analyst commits the approved decision in the **Right Panel**, which schedules the tasks and propagates the updates across the graph.

---

# Revised Sprint Roadmap

The roadmap sequence is revised to prioritize the flagship workspace and support a workflow-driven layout.

```
Sprint 38: Foundation ──▶ Sprint 39: Components ──▶ Sprint 40: Attack Surface & Security Intelligence Workspace MVP
                                                               │
┌──────────────────────────────────────────────────────────────┘
│
▼
Sprint 41: Threat & Graph Explorer ──▶ Sprint 42: Decisions & Gantt Workbench
                                                    │
┌───────────────────────────────────────────────────┘
│
▼
Sprint 43: GRC Console ──▶ Sprint 44: SOC & Resilience ──▶ Sprint 45: Executive Decision Intel
                                                                      │
┌─────────────────────────────────────────────────────────────────────┘
│
▼
Sprint 46: SaaS Multi-Tenancy ──▶ Sprint 47: Saved Whiteboards ──▶ Sprint 48: Copilot Workspace
```

---

### Sprint 38: Frontend Platform Foundation (Complete)
- **Objective**: Deliver authentication, API clients, JWT token refresh interceptors, and basic RBAC route guards.
- **Value**: Establishes the security baseline and API network layer.

### Sprint 39: Shared UI Library & Core Integration (Complete)
- **Objective**: Build the shared UI component framework and integrate MSW mocks to handle scopes onboarding, findings lists, and reports.
- **Value**: Prepares reusable UI blocks (`DataTable`, `ConfirmDialog`, `EmptyState`, `StatusBadge`).

### Sprint 40: Attack Surface & Security Intelligence Workspace (MVP)
- **Objective**: Implement the three-panel Unified Workspace layout integrating Asset Inventory, Attack Surface Changes, SVG Relationship Graph, and Decision actions.
- **Value**: Delivers immediate time-to-value by combining AegisX's original ASM DNA (internet-facing asset changes, unmanaged targets) with end-to-end decision intelligence on a single screen.

### Sprint 41: Threat Intelligence & Graph Topology Explorer
- **Objective**: Deepen threat feeds integration, support SVG/Canvas topology exploration, and implement attack path highlighting.
- **Value**: Enhances the Center Panel of the Unified Workspace with multi-hop relationship traversals.

### Sprint 42: Decision Tradeoffs & Planning Gantt Workbench
- **Objective**: Implement cost vs risk-reduction tradeoff plots, commitment controls, and Gantt roadmap timelines.
- **Value**: Enhances the Right Panel with financial prioritization metrics and task scheduling.

### Sprint 43: GRC Audit Console & Evidence Locker
- **Objective**: Build the compliance checklists, gaps editors, and evidence upload panels.
- **Value**: Exposes compliance framework status and automates audit preparation.

### Sprint 44: Cyber Resilience & SOC Analytics Dashboard
- **Objective**: Implement RTO/RPO compliance tracking, MTTR histograms, and active analyst queues.
- **Value**: Provides visibility into operational workloads and disaster recovery readiness.

### Sprint 45: Executive Decision Intelligence
- **Objective**: Implement executive dashboards displaying loss expectancy curves, ROSI metrics, and automated narratives.
- **Value**: Prepares AegisX for CISO and board-level reporting workflows.

### Sprint 46: Multi-Tenant SaaS Workspace & SSO
- **Objective**: Implement tenant switchers, enterprise workspace directories, and SAML/OIDC configuration panels.
- **Value**: Prepares the platform for secure, multi-tenant SaaS deployments.

### Sprint 47: Saved Whiteboards & Custom Exporters
- **Objective**: Deliver saved whiteboards and drag-and-drop report layout builders.
- **Value**: Enables analysts to save investigation layouts and CISOs to export custom posture reports.

### Sprint 48: Security Intelligence Copilot
- **Objective**: Integrate a slide-out chat drawer providing explainable, read-only advisory recommendations.
- **Value**: Accelerates threat investigations and decision processes using natural language assistance.

---

# Executive Decision Intelligence (Sprint 45 Design)

### Business Value
Translates technical vulnerability data into business metrics (such as financial risk and return on investment). This view aligns security spending with risk reduction, making it easier to present security updates to executive boards.

### Screens
- **CISO Executive Dashboard (`/executive`)**: High-level dashboard displaying risk curves, budget tradeoff sliders, and automated narratives.
- **Report Exporter Console**: Panel to configure and export executive reports.

### Key Components
- **`RiskLossCurve`**: SVG chart displaying annual loss expectancy curves (current vs projected).
- **`ROSIWidget`**: Scorecard displaying the Return on Security Investment percentage.
- **`BudgetSlider`**: Interactive slider simulating how budget allocations affect risk reduction.
- **`ExecutiveNarrative`**: Text box rendering automated summaries of risk posture changes.

### State Management
- React Query managing executive metrics.
- Zustand store managing active budget simulation parameters.

---

# Security Intelligence Copilot (Sprint 48 Design)

### Safety Constraints
- **Advisory Only**: The Copilot cannot execute commands or alter system configurations.
- **Read-Only**: Access is limited to reading data from the query API.
- **Explainable**: Recommendations must include citations and links back to the source assets, findings, and playbooks in the workspace.

### UI Architecture
- **Copilot Sidebar Drawer**: A slide-out panel accessible across all workspaces.
- **Reference Tags**: Citations inside chat responses display as clickable links, highlighting the corresponding node in the graph workspace.

### Audit Requirements
- All user prompts and Copilot responses are logged to the backend audit trail, tracking the active user, scope context, and timestamps.

### Deliverables
- Interactive chat interface component.
- Citations mapper linking text responses back to graph nodes.
- Prompt history viewer showing past queries.

---

# Final Recommendation

1. **Adopt Roadmap V2.1**: Restructure the sprint sequence to prioritize the Unified Workspace in Sprint 40.
2. **Implement the Three-Panel Design**: Follow the Left-Center-Right layout for the Unified Workspace to display the complete workflow on a single screen.
3. **Execute Sprints 45 & 48**: Implement the Executive dashboard and Copilot interfaces to prepare AegisX for commercial launch.
