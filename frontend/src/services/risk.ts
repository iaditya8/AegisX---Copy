import { apiClient } from './api';
import { StandardResponse } from '../types/common';

export interface CyberRisk {
  id: string;
  title: string;
  description: string;
  scenario_type: string;
  frequency_label: string;
  impact_label: string;
  exposure_value: number;
  annualized_loss_expectancy: number;
  inherent_risk_score: number;
  residual_risk_score: number;
  status: string;
  scope_id?: string;
  created_at: string;
}

export interface RiskForecast {
  scenario_type: string;
  p10_loss: number;
  p50_loss: number;
  p90_loss: number;
  simulated_mean: number;
}

export const riskService = {
  async getRisks(scopeId?: string): Promise<CyberRisk[]> {
    const response = await apiClient.get<any, StandardResponse<CyberRisk[]>>('/cyber-risk-quantification', {
      params: scopeId ? { scope_id: scopeId } : {},
    });
    return response.data || [];
  },

  async getForecasts(riskId: string): Promise<RiskForecast[]> {
    const response = await apiClient.get<any, StandardResponse<RiskForecast[]>>('/cyber-risk-quantification/forecasts', {
      params: { risk_id: riskId },
    });
    return response.data || [];
  },

  async getTrends(riskId: string): Promise<number[]> {
    const response = await apiClient.get<any, StandardResponse<number[]>>('/cyber-risk-quantification/trends', {
      params: { risk_id: riskId },
    });
    return response.data || [];
  },

  async getSummary(scopeId?: string): Promise<any> {
    const response = await apiClient.get<any, StandardResponse<any>>('/cyber-risk-quantification/summary', {
      params: scopeId ? { scope_id: scopeId } : {},
    });
    return response.data;
  },
};
