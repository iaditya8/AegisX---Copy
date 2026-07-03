export const QUERY_KEYS = {
  scopes: {
    list: ['scopes', 'list'] as const,
    detail: (id: string) => ['scopes', 'detail', id] as const,
    assets: (id: string, filters: any) => ['scopes', 'assets', id, filters] as const,
  },
  findings: {
    list: (filters: any) => ['findings', 'list', filters] as const,
    detail: (id: string) => ['findings', 'detail', id] as const,
    evidence: (id: string) => ['findings', 'evidence', id] as const,
  },
  workflows: {
    list: ['workflows', 'list'] as const,
    detail: (id: string) => ['workflows', 'detail', id] as const,
    events: (id: string) => ['workflows', 'events', id] as const,
  },
  scanRuns: {
    detail: (id: string) => ['scan_runs', 'detail', id] as const,
  },
  reports: {
    executive: ['reports', 'executive'] as const,
    findings: (filters: any) => ['reports', 'findings', filters] as const,
    exposure: ['reports', 'exposure'] as const,
    dashboardSummary: ['dashboard', 'summary'] as const,
    trends: (days: number) => ['dashboard', 'trends', { days }] as const,
  },
  assets: {
    detail: (id: string) => ['assets', 'detail', id] as const,
    relationships: (id: string) => ['assets', 'relationships', id] as const,
    history: (id: string) => ['assets', 'history', id] as const,
    report: (id: string) => ['assets', 'report', id] as const,
  },
  threats: {
    list: (scopeId?: string) => ['threats', 'list', { scopeId }] as const,
    active: ['threats', 'active'] as const,
  },
  risk: {
    list: (scopeId?: string) => ['risk', 'list', { scopeId }] as const,
    forecasts: (riskId: string) => ['risk', 'forecasts', riskId] as const,
    trends: (riskId: string) => ['risk', 'trends', riskId] as const,
    summary: (scopeId?: string) => ['risk', 'summary', { scopeId }] as const,
  },
  decisions: {
    list: ['decisions', 'list'] as const,
    recommended: ['decisions', 'recommended'] as const,
  },
  graph: {
    topology: ['graph', 'topology'] as const,
    path: (sourceId: string, targetId: string) => ['graph', 'path', sourceId, targetId] as const,
  },
  planning: {
    list: ['planning', 'list'] as const,
  },
  grc: {
    assessments: ['grc', 'assessments'] as const,
    frameworks: ['grc', 'frameworks'] as const,
    gaps: (assessmentId: string) => ['grc', 'gaps', assessmentId] as const,
    summary: (scopeId?: string) => ['grc', 'summary', { scopeId }] as const,
  },
  resilience: {
    list: ['resilience', 'list'] as const,
    objectives: (resilienceId: string) => ['resilience', 'objectives', resilienceId] as const,
    summary: (scopeId?: string) => ['resilience', 'summary', { scopeId }] as const,
  },
  soc: {
    queues: ['soc', 'queues'] as const,
    kpis: ['soc', 'kpis'] as const,
    analysts: ['soc', 'analysts'] as const,
  },
  executive: {
    reports: ['executive', 'reports'] as const,
    scorecard: (scopeId?: string) => ['executive', 'scorecard', { scopeId }] as const,
    heatmap: (scopeId?: string) => ['executive', 'heatmap', { scopeId }] as const,
  },
  posture: {
    summary: (scopeId?: string) => ['posture', 'summary', { scopeId }] as const,
    list: ['posture', 'list'] as const,
  },
  sso: {
    config: ['sso', 'config'] as const,
  },
  tenants: {
    list: ['tenants', 'list'] as const,
  },
  whiteboard: {
    list: ['whiteboard', 'list'] as const,
    detail: (id: string) => ['whiteboard', 'detail', id] as const,
  },
  copilot: {
    history: ['copilot', 'history'] as const,
  },
} as const;
