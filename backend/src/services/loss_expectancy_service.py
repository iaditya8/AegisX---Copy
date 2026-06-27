class LossExpectancyService:
    @classmethod
    def calculate_sle(cls, asset_value: float, exposure_factor: float) -> float:
        """Calculate Single Loss Expectancy: SLE = Asset Value * Exposure Factor."""
        return round(float(asset_value * exposure_factor), 2)

    @classmethod
    def calculate_ale(cls, sle: float, aro: float) -> float:
        """Calculate Annualized Loss Expectancy: ALE = SLE * ARO."""
        return round(float(sle * aro), 2)

    @classmethod
    def calculate(cls) -> None:
        """Calculates derived loss values for active risks in-memory (no mutation, read-only)."""
        pass
