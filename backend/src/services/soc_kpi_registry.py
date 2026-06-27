from typing import Set


class SOCKPIRegistry:
    KPIS = {
        "Mean Time To Detect (MTTD)",
        "Mean Time To Respond (MTTR)",
        "Mean Time To Contain (MTTC)",
        "Mean Time To Resolve",
        "Alert Closure Rate",
        "Case Closure Rate",
        "Incident Closure Rate",
        "Analyst Utilization",
        "Queue Processing Rate",
    }

    @classmethod
    def list_types(cls) -> Set[str]:
        """List all supported operational KPIs."""
        return cls.KPIS

    @classmethod
    def validate(cls, kpi_name: str) -> bool:
        """Validate if a KPI is supported."""
        return str(kpi_name).strip() in cls.KPIS
