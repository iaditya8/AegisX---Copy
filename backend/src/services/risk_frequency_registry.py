from typing import Dict, List


class RiskFrequencyRegistry:
    FREQUENCIES = {
        "RARE": 0.05,
        "OCCASIONAL": 0.2,
        "LIKELY": 1.0,
        "FREQUENT": 3.0,
    }

    @classmethod
    def get_aro(cls, label: str) -> float:
        """Resolve deterministic ARO (Annualized Rate of Occurrence) for a frequency label."""
        return cls.FREQUENCIES.get(str(label).strip().upper(), 1.0)

    @classmethod
    def list_frequencies(cls) -> List[str]:
        """List all supported frequency labels."""
        return list(cls.FREQUENCIES.keys())

    @classmethod
    def validate(cls, label: str) -> bool:
        """Validate if a frequency label is supported."""
        return str(label).strip().upper() in cls.FREQUENCIES
