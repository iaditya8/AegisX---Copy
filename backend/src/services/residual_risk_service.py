class ResidualRiskService:
    @classmethod
    def calculate_inherent_risk_score(cls, exposure_value: float, factor: float, aro: float) -> float:
        """Calculate deterministic inherent risk score from exposure, factor, and rate of occurrence."""
        if exposure_value <= 0:
            return 0.0
        # Scale to 0-100
        score = (exposure_value / 100000.0) * aro * factor * 100.0
        return round(min(100.0, max(0.0, score)), 2)

    @classmethod
    def calculate_residual_risk_score(cls, inherent_score: float, mitigation_effectiveness: float) -> float:
        """Calculate deterministic residual risk score: residual = inherent * (1 - mitigation_effectiveness / 100)."""
        factor = max(0.0, min(100.0, mitigation_effectiveness)) / 100.0
        return round(inherent_score * (1.0 - factor), 2)

    @classmethod
    def calculate_mitigation_effectiveness(cls, inherent_score: float, residual_score: float) -> float:
        """Derive mitigation effectiveness percentage: effectiveness = (inherent - residual) / inherent * 100."""
        if inherent_score <= 0.0:
            return 100.0
        eff = ((inherent_score - residual_score) / inherent_score) * 100.0
        return round(min(100.0, max(0.0, eff)), 2)

    @classmethod
    def calculate(cls) -> None:
        """Residual calculations for active risk records (read-only derived intelligence)."""
        pass
