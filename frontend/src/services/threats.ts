import { apiClient } from './api';

export interface Threat {
  id: string;
  value: string;
  indicator_type: string;
  status: string;
  source: string;
  tags: string[];
  scope_id?: string;
  fusion_score?: number;
  created_at: string;
  updated_at: string;
}

export const threatService = {
  async getThreats(scopeId?: string): Promise<Threat[]> {
    const response = await apiClient.get<any, any>('/threat-intelligence', {
      params: scopeId ? { scope_id: scopeId } : {},
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getActiveThreats(): Promise<Threat[]> {
    const response = await apiClient.get<any, any>('/threat-intelligence/active');
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async fuseThreat(id: string, confidence: number): Promise<Threat> {
    const response = await apiClient.post<any, any>(`/threat-intelligence/${id}/fuse`, {
      confidence,
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },
};
