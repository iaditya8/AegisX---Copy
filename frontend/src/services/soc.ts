import { apiClient } from './api';

export interface AnalystPerformance {
  id: string;
  analyst_name: string;
  cases_closed: number;
  mean_time_to_resolution_minutes: number;
  satisfaction_score: number;
}

export interface OperationalKPI {
  id: string;
  metric_name: string;
  metric_value: number;
  unit: string;
  target_value: number;
  status: 'optimal' | 'acceptable' | 'critical';
}

export interface QueueSummary {
  queue_name: string;
  active_tickets_count: number;
  oldest_ticket_age_hours: number;
  unassigned_tickets_count: number;
  critical_tickets_count: number;
  backlog_metrics?: {
    total_backlog_count: number;
    growth_rate_percent: number;
    estimated_clearance_days: number;
  };
}

export const socService = {
  async getQueueSummary(): Promise<QueueSummary> {
    const response = await apiClient.get<any, any>('/security-operations-analytics/queues');
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getKPIs(): Promise<OperationalKPI[]> {
    const response = await apiClient.get<any, any>('/security-operations-analytics/kpis');
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getAnalysts(): Promise<AnalystPerformance[]> {
    const response = await apiClient.get<any, any>('/security-operations-analytics/analysts');
    return response.success !== undefined ? response.data : (response.data || response);
  },
};
