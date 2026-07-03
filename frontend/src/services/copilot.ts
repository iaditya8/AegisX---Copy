import { apiClient } from './api';

export interface CopilotResponse {
  answer: string;
  citations: {
    id: string;
    type: 'asset' | 'finding' | 'threat' | 'playbook';
    label: string;
    link_url: string;
  }[];
}

export interface CopilotAuditTrail {
  id: string;
  user_id: string;
  scope_id?: string;
  prompt: string;
  response_text: string;
  created_at: string;
}

export const copilotService = {
  async askCopilot(prompt: string, scopeId?: string): Promise<CopilotResponse> {
    const response = await apiClient.post<any, any>('/copilot/ask', {
      prompt,
      scope_id: scopeId || null,
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getCopilotHistory(): Promise<CopilotAuditTrail[]> {
    const response = await apiClient.get<any, any>('/copilot/history');
    return response.success !== undefined ? response.data : (response.data || response);
  },
};
