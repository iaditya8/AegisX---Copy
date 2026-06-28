import { apiClient } from './api';

export interface Plan {
  id: string;
  category: string;
  name: string;
  status: string;
  priority: string;
  scope_id?: string;
  created_at: string;
}

export const planningService = {
  async getPlans(): Promise<Plan[]> {
    const response = await apiClient.get<any, any>('/autonomous-planning');
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async approvePlan(id: string): Promise<Plan> {
    const response = await apiClient.post<any, any>(`/autonomous-planning/${id}/approve`);
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async activatePlan(id: string): Promise<Plan> {
    const response = await apiClient.post<any, any>(`/autonomous-planning/${id}/activate`);
    return response.success !== undefined ? response.data : (response.data || response);
  },
};
