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
  }
} as const;
