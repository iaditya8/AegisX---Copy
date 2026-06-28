import uuid
from typing import Dict, List
from src.domain.entities.threat_intel import ThreatSeverity, ThreatFusionResponse


class ThreatIntelFusionService:
    @classmethod
    def calculate_fusion_score(cls, value: str, indicator_type: str) -> float:
        """Calculate deterministic threat fusion score from metadata."""
        score = float(len(value) * 4.5)
        return round(min(100.0, max(0.0, score)), 2)

    @classmethod
    def calculate(cls) -> None:
        """Run threat intelligence fusion calculations (read-only derived intelligence)."""
        pass
