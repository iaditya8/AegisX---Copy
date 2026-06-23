export interface DashboardFindingsSummary {
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export interface DashboardRiskSummary {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface DashboardSummary {
  asset_count: number;
  internet_exposed_assets: number;
  open_ports: number;
  services: number;
  findings: DashboardFindingsSummary;
  risk: DashboardRiskSummary;
}

export interface DashboardTrendPoint {
  timestamp: string;
  value: number;
}

export interface DashboardTrends {
  window_days: number;
  risk_trend: DashboardTrendPoint[];
  finding_trend: DashboardTrendPoint[];
  critical_finding_trend: DashboardTrendPoint[];
}

export interface ExecutiveReport {
  summary: Record<string, any>;
  top_risky_assets: Record<string, any>[];
  critical_findings: Record<string, any>[];
  risk_distribution: Record<string, number>;
  exposure_distribution: Record<string, number>;
}

export interface AssetReport {
  asset: Record<string, any>;
  exposure: Record<string, any>;
  risk: Record<string, any>;
  ports: Record<string, any>[];
  services: Record<string, any>[];
  technologies: string[];
  findings: Record<string, any>[];
}

export interface FindingReport {
  findings: Record<string, any>[];
  total_count: number;
}

export interface RiskReport {
  risk_distribution: Record<string, number>;
  critical_assets: Record<string, any>[];
  high_risk_assets: Record<string, any>[];
  risk_history: Record<string, any>[];
}

export interface ExposureReport {
  external_assets: Record<string, any>[];
  internal_assets: Record<string, any>[];
  unknown_assets: Record<string, any>[];
  internet_exposed_count: number;
}
