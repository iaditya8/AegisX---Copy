# Implementation Plan — Sprint 40: Attack Surface & Security Intelligence Workspace MVP

Implement the flagship three-panel workspace on the homepage (`/`), integrating Attack Surface Management (ASM) metrics, interactive SVG relationship graphs, FAIR risk scores, and decision mitigation actions.

---

## Goal Description

Establish AegisX's primary workspace, bridging its reconnaissance DNA (Asset inventories, unmanaged targets, delta changes) with advanced decision intelligence. This workspace enables analysts to run investigations and commit remediation plans on a single screen without context switching.

---

## Proposed Changes

```
 ┌────────────────────────────────────────────────────────┐
 │                 AegisX Unified Console                 │
 ├────────────────────────────────────────────────────────┤
 │                                                        │
 │  ┌─────────────────┐  ┌─────────────────┐  ┌────────┐  │
 │  │ LEFT PANEL      │  │ CENTER PANEL    │  │ RIGHT  │  │
 │  │                 │  │                 │  │ PANEL  │  │
 │  │ Attack Surface  │─▶│ SVG Topology    │─▶│ Risk & │  │
 │  │ & ASM           │  │ Relationship Map│  │ Decision│  │
 │  └─────────────────┘  └─────────────────┘  └────────┘  │
 └────────────────────────────────────────────────────────┘
```

### 1. Services & Hooks Layer

Create service files and React Query hooks to interface with the Sprints 24–37 backend endpoints.

#### [NEW] [threats.ts](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/frontend/src/services/threats.ts)
* Maps threats retrieval (`/threat-intelligence`) and threat actor profiles.
* Maps threat fusion mutation (`POST /threat-intelligence/fuse`).

#### [NEW] [risk.ts](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/frontend/src/services/risk.ts)
* Maps FAIR risk quantifications (`/cyber-risk-quantification`) and Monte Carlo forecasts.

#### [NEW] [decisions.ts](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/frontend/src/services/decisions.ts)
* Maps security decisions (`/security-decision`) and mitigation alternatives.
* Maps decision commits (`PUT /security-decision/commit`).

#### [NEW] [graph.ts](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/frontend/src/services/graph.ts)
* Maps relationship topology graphs (`/security-intelligence-graph`).

#### [NEW] [planning.ts](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/frontend/src/services/planning.ts)
* Maps autonomous plans (`/autonomous-planning`) and optimization tasks.

#### [NEW] [useWorkspace.ts](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/frontend/src/hooks/useWorkspace.ts)
* Custom react query query/mutation hooks wrapping the services above.

---

### 2. UI Components & Layout

Build the three-panel layout on the core dashboard route.

#### [MODIFY] [page.tsx](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/frontend/src/app/page.tsx)
* Replace the mock read-only dashboard layout with the flagship three-panel workspace structure.
* **Left Panel**:
  - Exposes Scope selector statistics (Total Assets, Managed vs Unmanaged ratio).
  - Highlights Attack Surface changes (subdomains or service changes discovered since last scan).
  - Displays target assets list and open vulnerability findings.
* **Center Panel**:
  - Renders an interactive SVG relationship graph showing the selected Asset.
  - Draws nodes for adjacent Findings (red), Threats (amber), and GRC Controls (green/red).
  - Visualizes critical attack paths using pulsating connections.
* **Right Panel**:
  - Displays the selected asset's FAIR Annualized Loss Expectancy projections.
  - Lists pending decision recommendations (e.g. "Implement ISO control") with cost vs risk-reduction values.
  - Includes a warning advisory badge and "Commit Plan" trigger buttons to dispatch tasks.

#### [NEW] [GraphCanvas.tsx](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/frontend/src/components/graph/GraphCanvas.tsx)
* Responsive SVG node-link renderer mapping asset nodes to adjacent alerts, compliance status, and target links.

---

### 3. Navigation Update

#### [MODIFY] [Sidebar.tsx](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/frontend/src/components/navigation/Sidebar.tsx)
* Enable and highlight the Dashboard link as the primary workspace portal.

---

## Verification Plan

### Automated Integration Tests

#### [NEW] [sprint40.test.tsx](file:///c:/Users/Aditya/Desktop/AegisX%20-%20Copy/frontend/src/sprint40.test.tsx)
Write an integration test suite validating:
- Left panel asset selection triggers graph center-focus updates.
- Center panel SVG graph renders asset relationships (Findings, Threats, GRC controls).
- Right panel calculates risk loss curves and pending tradeoffs list.
- Click confirmation on "Commit Plan" triggers the mock MSW decisions endpoint.

### Manual Verification
- Start Next.js dev server (`npm run dev`) and run unit tests (`npm test`) to confirm all 3 test files (`sprint38.test.tsx`, `sprint39.test.tsx`, and `sprint40.test.tsx`) pass successfully.
