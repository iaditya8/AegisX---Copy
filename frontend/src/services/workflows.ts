import { apiClient } from './api';
import { StandardResponse } from '../types/common';
import {
  Workflow,
  WorkflowCreate,
  ScanRun,
  WorkflowEvent,
  WorkflowStartRequest,
  WorkflowStartResponse,
} from '../types/workflow';
import {
  mapWorkflow,
  mapWorkflows,
  mapScanRun,
  mapWorkflowEvents,
} from '../mappers/workflowMapper';

export const workflowService = {
  async getWorkflows(params?: {
    page?: number;
    page_size?: number;
    owner_id?: string;
  }): Promise<StandardResponse<Workflow[]>> {
    const response = await apiClient.get<any, StandardResponse<any[]>>('/workflows', { params });
    return {
      ...response,
      data: mapWorkflows(response.data),
    };
  },

  async createWorkflow(data: WorkflowCreate): Promise<StandardResponse<Workflow>> {
    const response = await apiClient.post<any, StandardResponse<any>>('/workflows', data);
    return {
      ...response,
      data: mapWorkflow(response.data),
    };
  },

  async getWorkflowDetails(id: string): Promise<StandardResponse<Workflow>> {
    const response = await apiClient.get<any, StandardResponse<any>>(`/workflows/${id}`);
    return {
      ...response,
      data: mapWorkflow(response.data),
    };
  },

  async startWorkflow(id: string, data: WorkflowStartRequest): Promise<StandardResponse<WorkflowStartResponse>> {
    const response = await apiClient.post<any, StandardResponse<any>>(`/workflows/${id}/start`, data);
    return response;
  },

  async getWorkflowEvents(
    id: string,
    params?: { page?: number; page_size?: number }
  ): Promise<StandardResponse<WorkflowEvent[]>> {
    const response = await apiClient.get<any, StandardResponse<any[]>>(`/workflows/${id}/events`, { params });
    return {
      ...response,
      data: mapWorkflowEvents(response.data),
    };
  },

  async getScanRunDetails(id: string): Promise<StandardResponse<ScanRun>> {
    const response = await apiClient.get<any, StandardResponse<any>>(`/scan_runs/${id}`);
    return {
      ...response,
      data: mapScanRun(response.data),
    };
  },

  async cancelScanRun(id: string): Promise<StandardResponse<boolean>> {
    const response = await apiClient.post<any, StandardResponse<boolean>>(`/scan_runs/${id}/cancel`);
    return response;
  },
};
