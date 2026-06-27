from typing import Set


class AttackValidationRegistry:
    TECHNIQUES = {
        "T1059": "Command and Scripting Interpreter",
        "T1562": "Impair Defenses",
        "T1078": "Valid Accounts",
        "T1027": "Obfuscated Files",
        "T1105": "Ingress Tool Transfer",
        "T1047": "WMI",
        "T1055": "Process Injection",
    }

    @classmethod
    def get_registered_techniques(cls) -> Set[str]:
        """Retrieve all pre-seeded validation techniques."""
        return set(cls.TECHNIQUES.keys())

    @classmethod
    def is_valid_technique(cls, technique_id: str) -> bool:
        """Check if a technique is pre-seeded/registered."""
        return technique_id in cls.TECHNIQUES
