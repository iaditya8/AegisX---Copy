# Risk and Criticality Architecture

This document describes the design separation and relationship between **Asset Criticality** and **Risk Score** in AegisX.

## 1. Asset Criticality

Asset Criticality represents the **business importance** and **exposure profile** of a given asset. It is computed deterministically and indicates how critical the asset is to the business organization.

It is derived from:
- **Exposure**: Whether the asset is internet-exposed or purely internal.
- **Findings**: The presence and counts of high-severity vulnerabilities.
- **Services**: The number of open ports/services running.
- **Technologies**: The breadth of the software stack (products) present.

## 2. Risk Score

Risk Score represents the **technical risk posture** and active attack surface footprint of the asset.

It is derived from:
- **Risk Factors**: Specific conditions identified on the asset (e.g., `internet_exposed`, `multiple_open_ports`, `critical_finding_present`, etc.).
- **Correlation Engine**: The consolidated list of active vulnerabilities and technologies.
- **Risk Registry**: Centralized scoring weights mapped to each risk factor.

## 3. Relationship: Independence of Dimensions

In Sprint 9, **Asset Criticality** and **Risk Score** are designed as **independent dimensions**. An asset can have a high business criticality without having a high risk profile, and vice versa.

### Examples

- **High Criticality + Low/Medium Risk**:
  - A primary domain controller or production web app is classified as a critical asset because it runs many services and is internet-exposed. However, because it is actively patched and has no critical vulnerabilities, its Risk Score remains low or medium.
- **Low Criticality + High Risk**:
  - A development/staging asset running internally has a low criticality score. However, it runs outdated services with multiple critical vulnerabilities and open ports, leading to a high Risk Score.

> [!NOTE]
> Future sprints may choose to couple or scale Risk Scores based on Asset Criticality (e.g., using criticality as a multiplier for risk prioritization). In Sprint 9, they are kept independent to ensure clean, untangled prioritization inputs.
