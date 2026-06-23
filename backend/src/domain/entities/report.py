from typing import Any, Dict, List

from pydantic import BaseModel, Field


class DashboardFindingsSummary(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class DashboardRiskSummary(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class DashboardSummaryResponse(BaseModel):
    """Platform-wide aggregated metrics."""

    asset_count: int = 0
    internet_exposed_assets: int = 0
    open_ports: int = 0
    services: int = 0
    findings: DashboardFindingsSummary = Field(default_factory=DashboardFindingsSummary)
    risk: DashboardRiskSummary = Field(default_factory=DashboardRiskSummary)


class DashboardTrendPoint(BaseModel):
    """Single point in a time-series trend."""

    timestamp: str
    value: float


class DashboardTrendResponse(BaseModel):
    """Time-series trends for risk and findings."""

    window_days: int = 30
    risk_trend: List[DashboardTrendPoint] = Field(default_factory=list)
    finding_trend: List[DashboardTrendPoint] = Field(default_factory=list)
    critical_finding_trend: List[DashboardTrendPoint] = Field(default_factory=list)


class ExecutiveReportResponse(BaseModel):
    """High-level security posture report."""

    summary: Dict[str, Any] = Field(default_factory=dict)
    top_risky_assets: List[Dict[str, Any]] = Field(default_factory=list)
    critical_findings: List[Dict[str, Any]] = Field(default_factory=list)
    risk_distribution: Dict[str, int] = Field(default_factory=dict)
    exposure_distribution: Dict[str, int] = Field(default_factory=dict)


class AssetReportResponse(BaseModel):
    """Detailed report for a single asset."""

    asset: Dict[str, Any]
    exposure: Dict[str, Any]
    risk: Dict[str, Any]
    ports: List[Dict[str, Any]] = Field(default_factory=list)
    services: List[Dict[str, Any]] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    findings: List[Dict[str, Any]] = Field(default_factory=list)


class FindingReportResponse(BaseModel):
    """Filtered list of findings for reporting."""

    findings: List[Dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0


class RiskReportResponse(BaseModel):
    """Detailed risk intelligence report."""

    risk_distribution: Dict[str, int] = Field(default_factory=dict)
    critical_assets: List[Dict[str, Any]] = Field(default_factory=list)
    high_risk_assets: List[Dict[str, Any]] = Field(default_factory=list)
    risk_history: List[Dict[str, Any]] = Field(default_factory=list)


class ExposureReportResponse(BaseModel):
    """Asset distribution by network exposure."""

    external_assets: List[Dict[str, Any]] = Field(default_factory=list)
    internal_assets: List[Dict[str, Any]] = Field(default_factory=list)
    unknown_assets: List[Dict[str, Any]] = Field(default_factory=list)
    internet_exposed_count: int = 0
