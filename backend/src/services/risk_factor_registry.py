from typing import Dict

# Centralized registry of risk factors and their corresponding risk score impacts.
# Sum of all registered values is 100, which naturally maps factor accumulation to a 0-100 range.
RISK_FACTORS: Dict[str, int] = {
    "internet_exposed": 20,
    "critical_finding_present": 25,
    "high_finding_count": 15,
    "multiple_open_ports": 10,
    "multiple_services": 10,
    "high_attack_surface": 20,
}
