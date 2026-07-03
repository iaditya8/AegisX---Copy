import { apiClient } from './api';

export interface ResilienceRecord {
  id: string;
  title: string;
  description: string;
  service_name: string;
  service_criticality: 'low' | 'medium' | 'high' | 'critical';
  status: 'draft' | 'active' | 'validated' | 'completed' | 'closed';
  scope_id?: string;
  created_at: string;
  updated_at: string;
}

export interface RecoveryObjective {
  id: string;
  objective_name: string;
  target_rto_minutes: number;
  target_rpo_minutes: number;
  actual_rto_minutes?: number;
  actual_rpo_minutes?: number;
  status: 'achieved' | 'missed' | 'untested';
}

export const resilienceService = {
  async getResilienceRecords(): Promise<ResilienceRecord[]> {
    const response = await apiClient.get<any, any>('/cyber-resilience');
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getObjectives(resilienceId: string): Promise<RecoveryObjective[]> {
    const response = await apiClient.get<any, any>('/cyber-resilience/objectives', {
      params: { resilience_id: resilienceId },
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getSummary(scopeId?: string): Promise<any> {
    const response = await apiClient.get<any, any>('/cyber-resilience/summary', {
      params: scopeId ? { scope_id: scopeId } : {},
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async updateResilienceStatus(
    id: string,
    action: 'activate' | 'validate' | 'complete' | 'close'
  ): Promise<ResilienceRecord> {
    const response = await apiClient.post<any, any>(`/cyber-resilience/${id}/${action}`);
    return response.success !== undefined ? response.data : (response.data || response);
  },
};
