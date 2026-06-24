from typing import Dict

RISK_ACCEPTANCE_DAYS: Dict[str, int] = {
    "CRITICAL": 30,
    "HIGH": 60,
    "MEDIUM": 90,
    "LOW": 180,
}
