import {
  DashboardSummary,
  DashboardTrends,
  ExecutiveReport,
  AssetReport,
  FindingReport,
  RiskReport,
  ExposureReport
} from '../types/report';

export const mapDashboardSummary = (data: any): DashboardSummary => ({
  asset_count: data.asset_count || 0,
  internet_exposed_assets: data.internet_exposed_assets || 0,
  open_ports: data.open_ports || 0,
  services: data.services || 0,
  findings: {
    critical: data.findings?.critical || 0,
    high: data.findings?.high || 0,
    medium: data.findings?.medium || 0,
    low: data.findings?.low || 0,
    info: data.findings?.info || 0,
  },
  risk: {
    critical: data.risk?.critical || 0,
    high: data.risk?.high || 0,
    medium: data.risk?.medium || 0,
    low: data.risk?.low || 0,
  },
});

export const mapDashboardTrends = (data: any): DashboardTrends => ({
  window_days: data.window_days || 30,
  risk_trend: Array.isArray(data.risk_trend)
    ? data.risk_trend.map((pt: any) => ({ timestamp: pt.timestamp, value: pt.value }))
    : [],
  finding_trend: Array.isArray(data.finding_trend)
    ? data.finding_trend.map((pt: any) => ({ timestamp: pt.timestamp, value: pt.value }))
    : [],
  critical_finding_trend: Array.isArray(data.critical_finding_trend)
    ? data.critical_finding_trend.map((pt: any) => ({ timestamp: pt.timestamp, value: pt.value }))
    : [],
});

export const mapExecutiveReport = (data: any): ExecutiveReport => ({
  summary: data.summary || {},
  top_risky_assets: Array.isArray(data.top_risky_assets) ? data.top_risky_assets : [],
  critical_findings: Array.isArray(data.critical_findings) ? data.critical_findings : [],
  risk_distribution: data.risk_distribution || {},
  exposure_distribution: data.exposure_distribution || {},
});

export const mapAssetReport = (data: any): AssetReport => ({
  asset: data.asset || {},
  exposure: data.exposure || {},
  risk: data.risk || {},
  ports: Array.isArray(data.ports) ? data.ports : [],
  services: Array.isArray(data.services) ? data.services : [],
  technologies: Array.isArray(data.technologies) ? data.technologies : [],
  findings: Array.isArray(data.findings) ? data.findings : [],
});

export const mapFindingReport = (data: any): FindingReport => ({
  findings: Array.isArray(data.findings) ? data.findings : [],
  total_count: data.total_count || 0,
});

export const mapRiskReport = (data: any): RiskReport => ({
  risk_distribution: data.risk_distribution || {},
  critical_assets: Array.isArray(data.critical_assets) ? data.critical_assets : [],
  high_risk_assets: Array.isArray(data.high_risk_assets) ? data.high_risk_assets : [],
  risk_history: Array.isArray(data.risk_history) ? data.risk_history : [],
});

export const mapExposureReport = (data: any): ExposureReport => ({
  external_assets: Array.isArray(data.external_assets) ? data.external_assets : [],
  internal_assets: Array.isArray(data.internal_assets) ? data.internal_assets : [],
  unknown_assets: Array.isArray(data.unknown_assets) ? data.unknown_assets : [],
  internet_exposed_count: data.internet_exposed_count || 0,
});
