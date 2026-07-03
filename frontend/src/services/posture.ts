import { apiClient } from './api';

export interface PostureFinding {
  id: string;
  title: string;
  description: string;
  category: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'open' | 'mitigated' | 'accepted' | 'closed';
  risk_source: string;
  owner?: string;
  scope_id?: string;
  created_at: string;
}

export interface PostureSummary {
  total_count: number;
  open_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  drift_index?: number; // mock representation of delta indicators
}

export const postureService = {
  async getPostures(): Promise<PostureFinding[]> {
    const response = await apiClient.get<any, any>('/security-posture');
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getPostureSummary(scopeId?: string): Promise<PostureSummary> {
    const response = await apiClient.get<any, any>('/security-posture/summary', {
      params: scopeId ? { scope_id: scopeId } : {},
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async checkPostureDrift(scopeId?: string): Promise<any> {
    const response = await apiClient.get<any, any>('/security-posture/drift', {
      params: scopeId ? { scope_id: scopeId } : {},
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async updatePostureStatus(
    id: string,
    action: 'accept' | 'mitigate' | 'close'
  ): Promise<PostureFinding> {
    const response = await apiClient.post<any, any>(`/security-posture/${id}/${action}`);
    return response.success !== undefined ? response.data : (response.data || response);
  },
};
