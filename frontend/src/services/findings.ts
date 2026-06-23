import { apiClient } from './api';
import { StandardResponse } from '../types/common';
import { Finding, FindingEvidence } from '../types/finding';
import { mapFinding, mapFindings, mapFindingEvidences } from '../mappers/findingMapper';

export const findingService = {
  async getFindings(params?: {
    severity?: string;
    scanner?: string;
    scope_id?: string;
    asset_id?: string;
    page?: number;
    page_size?: number;
  }): Promise<StandardResponse<Finding[]>> {
    const response = await apiClient.get<any, StandardResponse<any[]>>('/findings', { params });
    return {
      ...response,
      data: mapFindings(response.data),
    };
  },

  async getFindingDetails(id: string): Promise<StandardResponse<Finding>> {
    const response = await apiClient.get<any, StandardResponse<any>>(`/findings/${id}`);
    return {
      ...response,
      data: mapFinding(response.data),
    };
  },

  async acknowledgeFinding(id: string): Promise<StandardResponse<Finding>> {
    const response = await apiClient.post<any, StandardResponse<any>>(`/findings/${id}/ack`);
    return {
      ...response,
      data: mapFinding(response.data),
    };
  },

  async resolveFinding(id: string): Promise<StandardResponse<Finding>> {
    const response = await apiClient.post<any, StandardResponse<any>>(`/findings/${id}/resolve`);
    return {
      ...response,
      data: mapFinding(response.data),
    };
  },

  async suppressFinding(id: string): Promise<StandardResponse<Finding>> {
    const response = await apiClient.post<any, StandardResponse<any>>(`/findings/${id}/suppress`);
    return {
      ...response,
      data: mapFinding(response.data),
    };
  },

  async getFindingEvidence(id: string): Promise<StandardResponse<FindingEvidence[]>> {
    const response = await apiClient.get<any, StandardResponse<any[]>>(`/findings/${id}/evidence`);
    return {
      ...response,
      data: mapFindingEvidences(response.data),
    };
  },
};
