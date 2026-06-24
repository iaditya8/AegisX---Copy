from typing import Any, Dict

CONTROL_MAPPINGS: Dict[str, str] = {
    "critical_vulnerability": "VULN-001",
    "internet_exposed_admin_service": "EXP-001",
    "sla_breach": "OPS-001",
    "accepted_risk": "GOV-001",
}

CONTROL_DETAILS: Dict[str, Dict[str, Any]] = {
    "VULN-001": {
        "name": "Critical Vulnerability Management",
        "severity": "HIGH",
    },
    "EXP-001": {
        "name": "Exposed Administrative Services",
        "severity": "CRITICAL",
    },
    "OPS-001": {
        "name": "Remediation SLA Compliance",
        "severity": "MEDIUM",
    },
    "GOV-001": {
        "name": "Formal Risk Acceptance Governance",
        "severity": "LOW",
    },
}
