import { apiClient } from './api';
import { StandardResponse } from '../types/common';
import {
  DashboardSummary,
  DashboardTrends,
  ExecutiveReport,
  AssetReport,
  FindingReport,
  RiskReport,
  ExposureReport,
} from '../types/report';
import {
  mapDashboardSummary,
  mapDashboardTrends,
  mapExecutiveReport,
  mapAssetReport,
  mapFindingReport,
  mapRiskReport,
  mapExposureReport,
} from '../mappers/reportMapper';

export const reportService = {
  async getDashboardSummary(): Promise<StandardResponse<DashboardSummary>> {
    const response = await apiClient.get<any, StandardResponse<any>>('/dashboard/summary');
    return {
      ...response,
      data: mapDashboardSummary(response.data),
    };
  },

  async getDashboardTrends(params?: { days?: number }): Promise<StandardResponse<DashboardTrends>> {
    const response = await apiClient.get<any, StandardResponse<any>>('/dashboard/trends', { params });
    return {
      ...response,
      data: mapDashboardTrends(response.data),
    };
  },

  async getExecutiveReport(): Promise<StandardResponse<ExecutiveReport>> {
    const response = await apiClient.get<any, StandardResponse<any>>('/reports/executive');
    return {
      ...response,
      data: mapExecutiveReport(response.data),
    };
  },

  async getAssetReport(id: string): Promise<StandardResponse<AssetReport>> {
    const response = await apiClient.get<any, StandardResponse<any>>(`/reports/assets/${id}`);
    return {
      ...response,
      data: mapAssetReport(response.data),
    };
  },

  async getFindingsReport(params?: {
    severity?: string;
    status?: string;
    template?: string;
    asset_id?: string;
  }): Promise<StandardResponse<FindingReport>> {
    const response = await apiClient.get<any, StandardResponse<any>>('/reports/findings', { params });
    return {
      ...response,
      data: mapFindingReport(response.data),
    };
  },

  async getRiskReport(): Promise<StandardResponse<RiskReport>> {
    const response = await apiClient.get<any, StandardResponse<any>>('/reports/risk');
    return {
      ...response,
      data: mapRiskReport(response.data),
    };
  },

  async getExposureReport(): Promise<StandardResponse<ExposureReport>> {
    const response = await apiClient.get<any, StandardResponse<any>>('/reports/exposure');
    return {
      ...response,
      data: mapExposureReport(response.data),
    };
  },

  async exportExecutiveReportJson(): Promise<Blob> {
    const response = await apiClient.get<any, any>('/reports/executive/export/json', {
      responseType: 'blob',
    });
    // response will be the full AxiosResponse object because data.success is undefined (it's a blob)
    return response.data;
  },

  async exportExecutiveReportCsv(): Promise<Blob> {
    const response = await apiClient.get<any, any>('/reports/executive/export/csv', {
      responseType: 'blob',
    });
    return response.data;
  },

  async exportAssetReportJson(id: string): Promise<Blob> {
    const response = await apiClient.get<any, any>(`/reports/assets/${id}/export/json`, {
      responseType: 'blob',
    });
    return response.data;
  },

  async exportAssetReportCsv(id: string): Promise<Blob> {
    const response = await apiClient.get<any, any>(`/reports/assets/${id}/export/csv`, {
      responseType: 'blob',
    });
    return response.data;
  },
};
