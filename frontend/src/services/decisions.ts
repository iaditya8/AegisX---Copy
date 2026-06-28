import { apiClient } from './api';

export interface Decision {
  id: string;
  decision_type: string;
  target_entity_id: string;
  option_name: string;
  status: string;
  scope_id?: string;
  created_at: string;
}

export const decisionService = {
  async getDecisions(): Promise<Decision[]> {
    const response = await apiClient.get<any, any>('/security-decision');
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getRecommendedDecisions(): Promise<Decision[]> {
    const response = await apiClient.get<any, any>('/security-decision/recommended');
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async commitDecision(id: string): Promise<Decision> {
    const response = await apiClient.post<any, any>(`/security-decision/${id}/commit`);
    return response.success !== undefined ? response.data : (response.data || response);
  },
};
