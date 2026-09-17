# AegisX Final Demo Walkthrough Guide
## (Frontend UAT / Mock Backend Validation)

---

## 1. Introduction

Welcome to the AegisX Final Demo Walkthrough! This guide provides a step-by-step path for demonstrating AegisX's flagship three-panel workspace, cybersecurity triage tools, GRC console, SOC operations, and AI Copilot capability using the local development server running on `http://localhost:3000`.

Due to local machine WSL virtual disk failures, this walkthrough runs in **Mock Backend Validation** mode, utilizing the built-in **Mock Service Worker (MSW)** client-side engine. MSW intercepts all outbound network calls and provides rich, interactive mock data, allowing stakeholders to experience the entire app walkthrough natively.

---

## 2. Interactive Step-by-Step Demo Tour

### Step 1: Secure Analyst Login
1. Open your browser and navigate to `http://localhost:3000/login`.
2. View the clean dark-mode login portal.
3. Enter username: `analyst_admin` and password: `password` (any input will be accepted by the mock auth system).
4. Click **"Sign In"**. You will be immediately authorized and routed to the unified workspace.

---

### Step 2: Flagship Three-Panel Workspace
Upon login, you are presented with the primary workspace designed to prevent context-switching for analysts:

1. **Left Panel (Reconnaissance & Inventory):**
   * View scope context stats (e.g. Total Assets, Managed vs Unmanaged ratio).
   * Review target assets list (e.g. `host.example.com`).
2. **Center Panel (Interactive SVG Relationship Graph):**
   * Observe the visual topology map.
   * Nodes represent Assets (blue), Findings (red/amber), and GRC Controls (green).
   * Connections show propagation paths and dependency ties.
3. **Right Panel (FAIR Projections & Decision Commit):**
   * Review the Monte Carlo forecast curves showing Annualized Loss Expectancy.
   * Look at the pending tradeoff recommendations list (e.g. `"Deploy WAF & Restrict Ingress Port 8080"`).
   * Click the **"Commit Mitigation Plan"** button. The interface will display success feedback indicating that the plan was successfully committed.

---

### Step 3: Vulnerability Findings Log & Triage
1. Click **"Findings"** in the sidebar to open the master log (`/findings`).
2. View the table of open vulnerabilities (e.g. `"Outdated Nginx Version Detection"`).
3. Click the details link to view `/findings/finding-123`.
4. Review the details card and click **"Acknowledge"**.
5. Observe the status badge transition to green **"acknowledged"**, showing how easily analysts can track triage status.

---

### Step 4: Governance, Risk, & Compliance (GRC)
1. Click **"GRC"** in the sidebar (`/grc`).
2. View the ISO 27001 Compliance Audit status card.
3. Review the identified gaps list (e.g. `"Management of technical vulnerabilities"`).
4. Click the status action buttons to simulate checking or updating GRC assessments.

---

### Step 5: SOC Operations Dashboard
1. Click **"SOC"** in the sidebar (`/soc`).
2. View the Primary SOC Triage Queue, which displays active tickets (14), unassigned tickets (3), and backlog estimations.
3. Look at the SOC Analyst Performance cards detailing Sarah Connor and John Miller's case clearance speeds.

---

### Step 6: Executive Posture & Scorecards
1. Click **"Executive"** in the sidebar (`/executive`).
2. View the overall security posture grade (**B+**) and the Risk Score (**78**).
3. Review the likelihood-impact Heatmap coordinates.
4. Click **"Export Platform CSV"** to verify browser-side report file generation.

---

### Step 7: Saved Whiteboards Workspace
1. Click **"Whiteboards"** in the sidebar (`/whiteboards`).
2. Select the `"APT-41 Exploit Path Analysis"` item.
3. Review the visual whiteboard topology nodes and the analyst notes panel.

---

### Step 8: Scan Workflows catalog
1. Click **"Workflows"** in the sidebar (`/workflows`).
2. Click **"Launch Run"** on the Basic Vulnerability Scan.
3. Confirm in the dialog. You will be redirected to the task progress tracker, showing streamed background scan logs.

---

### Step 9: AI Copilot Assistant Drawer
1. Click the Copilot/Chat icon in the topbar header to slide out the Copilot panel.
2. Enter the prompt: `Show posture issues` and click send.
3. View the generated response and interact with the clickable markdown citations, which highlight exact findings and assets.

---

### Step 10: Logout
1. Click **"Logout"** in the topbar or sidebar.
2. Confirm the action to safely clear all session states and return to the secure login page.
