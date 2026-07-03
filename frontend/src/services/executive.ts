import { apiClient } from './api';

export interface ExecutiveReport {
  id: string;
  title: string;
  description: string;
  report_period: string;
  report_type: string;
  status: 'draft' | 'published' | 'archived';
  scope_id?: string;
  created_at: string;
}

export interface ExecutiveScorecard {
  grade: string;
  risk_score: number;
  total_findings_count: number;
  critical_findings_count: number;
  high_findings_count: number;
  status: 'optimal' | 'warning' | 'critical';
}

export interface HeatmapCoord {
  likelihood: number;
  impact: number;
  count: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
}

export interface ExecutiveHeatmap {
  coordinates: HeatmapCoord[];
}

export const executiveService = {
  async getReports(): Promise<ExecutiveReport[]> {
    const response = await apiClient.get<any, any>('/executive-reporting');
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getScorecard(scopeId?: string): Promise<ExecutiveScorecard> {
    const response = await apiClient.get<any, any>('/executive-reporting/scorecard', {
      params: scopeId ? { scope_id: scopeId } : {},
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getHeatmap(scopeId?: string): Promise<ExecutiveHeatmap> {
    const response = await apiClient.get<any, any>('/executive-reporting/heatmap', {
      params: scopeId ? { scope_id: scopeId } : {},
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async createReport(
    title: string,
    description: string,
    period: string,
    type: string,
    scopeId?: string
  ): Promise<ExecutiveReport> {
    const response = await apiClient.post<any, any>('/executive-reporting', {
      title,
      description,
      report_period: period,
      report_type: type,
      scope_id: scopeId || null,
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async transitionReportStatus(
    id: string,
    status: 'draft' | 'published' | 'archived'
  ): Promise<ExecutiveReport> {
    const response = await apiClient.post<any, any>(`/executive-reporting/${id}/transition`, {
      status,
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },
};
